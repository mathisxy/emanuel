import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
import secrets
from datetime import datetime
from typing import List, Dict

from attr import dataclass
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.logging import LogMessage
from mcp import Tool

from core.config import Config
from discord_message import DiscordMessage, DiscordMessageFileTmp, DiscordMessageReplyTmp, DiscordMessageProgressTmp, \
    DiscordMessageRemoveTmp, DiscordMessageFile, DiscordMessageReply
from providers.base import BaseLLM, LLMToolCall
from providers.utils.chat import LLMChat
from providers.utils.ollama_error_reasoning import error_reasoning
from providers.utils.response_filtering import filter_response
from providers.utils.tool_calls import mcp_to_dict_tools, get_custom_tools_system_prompt, get_tools_system_prompt
from providers.utils.vram import wait_for_vram


async def generate_with_mcp(llm: BaseLLM, chat: LLMChat, queue: asyncio.Queue[DiscordMessage | None], use_help_bot: bool = False):

    async def log_handler(message: LogMessage):
        if message.data.get("msg") == "preview_image":
            image_base64 = message.data.get("extra").get("base64")
            image_type = message.data.get("extra").get("type")
            image_bytes = base64.b64decode(image_base64)
            await queue.put(DiscordMessageFileTmp(value=image_bytes, filename=f"preview.{image_type}", key="progress"))
        else:
            await queue.put(DiscordMessageReplyTmp(value=str(message.data.get("msg")), key=message.level.lower()))
    async def progress_handler(progress: float, total: float|None, message: str|None):
        logging.debug(f"PROGRESS: {progress}/{total}:{message}")
        await queue.put(DiscordMessageProgressTmp(progress=progress, total=total, key="progress"))

    if not Config.MCP_SERVER_URL:
        raise Exception("Kein MCP Server URL verfügbar")
    client = Client(Config.MCP_SERVER_URL, log_handler=log_handler, progress_handler=progress_handler)

    async with client:

        mcp_tools = await client.list_tools()

        mcp_tools = filter_tool_list(mcp_tools)
        mcp_dict_tools = mcp_to_dict_tools(mcp_tools)

        logging.info(mcp_tools)
        logging.info(mcp_dict_tools)

        if not Config.TOOL_INTEGRATION:
            chat.system_entry["content"] += get_custom_tools_system_prompt(mcp_tools, Config.LANGUAGE)
        else:
            chat.system_entry["content"] += get_tools_system_prompt(Config.LANGUAGE)

        tool_call_errors = False

        for i in range(Config.MAX_TOOL_CALLS):

            logging.info(f"Tool Call Errors: {tool_call_errors}")

            await wait_for_vram(required_gb=11)

            deny_tools = Config.DENY_RECURSIVE_TOOL_CALLING and not tool_call_errors and i > 0

            use_integrated_tools = Config.TOOL_INTEGRATION and not deny_tools

            logging.info(f"Use integrated tools: {use_integrated_tools}")

            response = await llm.generate(chat, tools= mcp_to_dict_tools(mcp_tools) if use_integrated_tools else None)

            if response.text:

                chat.history.append({"role": "assistant", "content": response.text})
                await queue.put(DiscordMessageReply(filter_response(response.text, Config.OLLAMA_MODEL)))

            if deny_tools:
                break

            try:
                if Config.TOOL_INTEGRATION and response.tool_calls:
                    tool_calls = response.tool_calls
                else:
                    tool_calls = extract_custom_tool_calls(response.text)

                tool_call_errors = False

            except Exception as e:

                logging.error(e, exc_info=True)

                if Config.HELP_DISCORD_ID and use_help_bot:
                    await queue.put(DiscordMessageReplyTmp("error", f"<@{Config.HELP_DISCORD_ID}> Ein Fehler ist aufgetreten: {e}", embed=False))
                    break

                try:
                    await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Aufgetretener Fehler wird analysiert..."))
                    reasoning = await error_reasoning(str(e), chat)

                except Exception as f:
                    logging.error(f)
                    reasoning = str(e)

                finally:
                    await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                chat.history.append({"role": "system", "content": reasoning})
                tool_call_errors = True

                continue


            if tool_calls:

                tool_results = []
                tool_image_results = []
                tool_file_results = []

                for tool_call in tool_calls:

                    logging.info(f"TOOL CALL: {tool_call}")

                    name = tool_call.name
                    arguments = tool_call.arguments


                    try:

                        formatted_args = "\n".join(f" - **{k}:** {v}" for k, v in arguments.items())
                        await queue.put(DiscordMessageReplyTmp(name, f"Das Tool {name} wird aufgerufen:\n{formatted_args}"))

                        result = await client.call_tool(name, arguments)

                        logging.info(f"Tool Call Result bekommen für {name}")

                        if not result.content:
                            logging.warning("Kein Tool Result Content, manuelle Unterbrechung")
                            break # Manuelle Unterbrechung

                        else:

                            if use_integrated_tools:
                                chat.history.append({"role": "assistant", "content": f"#<function_call>{tool_call}</function_call>"})

                            process_tool_result(name, result, tool_results, tool_image_results, tool_file_results)

                    except Exception as e:
                        logging.exception("Fehler aufgetreten: %s", e, exc_info=True)

                        if Config.HELP_DISCORD_ID and use_help_bot:
                            await queue.put(DiscordMessageReplyTmp("error", f"<@{Config.HELP_DISCORD_ID}> Ein Fehler ist aufgetreten: {e}", embed=False))
                            break

                        try:
                            await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Aufgetretener Fehler wird analysiert..."))
                            reasoning = await error_reasoning(str(e), chat)

                        except Exception:
                            await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Analysieren des Fehlers fehlgeschlagen"))
                            reasoning = str(e)

                        finally:
                            await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                        tool_results.append({name: reasoning})

                        tool_call_errors = True


                if tool_results:
                    tool_results_message = f"#{json.dumps({"tool_results": tool_results})}"

                    logging.info(tool_results_message)

                    chat.history.append({"role": "system", "content": tool_results_message})

                for image_content, filename in tool_image_results:
                    await queue.put(DiscordMessageFile(image_content, filename))
                    chat.history.append({"role": "assistant", "content": "", "images": [os.path.join("downloads", filename)]})

                for file_content, filename in tool_file_results:
                    await queue.put(DiscordMessageFile(file_content, filename))
                    chat.history.append({"role": "assistant", "content": f"Du hast eine Datei gesendet: {filename}"})


                logging.info(chat.history)

                if not tool_results:
                    break

            else:
                break


def filter_tool_list(tools: List[Tool]):

    tags = Config.MCP_TOOL_TAGS
    logging.info(tags)

    return [
        tool for tool in tools
        if hasattr(tool, 'meta') and tool.meta and
           tool.meta.get('_fastmcp', {}) and
           any(tag in tool.meta['_fastmcp'].get('tags', []) for tag in tags)
    ]


def extract_custom_tool_calls(text: str) -> List[LLMToolCall]:
    tool_calls = []
    pattern = r'```tool(.*?)```'

    matches = re.findall(pattern, text, flags=re.DOTALL)
    for raw in matches:
        raw_json = raw.strip()
        try:
            tool_call_data = json.loads(raw_json)
            llm_tool_call = LLMToolCall(tool_call_data.get("name"), tool_call_data.get("arguments", []))
            tool_calls.append(llm_tool_call)
        except json.JSONDecodeError as e:
            raise Exception(f"Fehler beim JSON Dekodieren des Tool Calls: {e}")

    return tool_calls

def process_tool_result(name: str, result: CallToolResult, tool_results: List, tool_image_results: List, tool_file_results: List):

    if not result.content:
        raise Exception(f"Das Tool Result hat keinen Inhalt.")
    logging.info(result.content[0].type)

    if result.content[0].type == "text":
        logging.info(result.content[0].text)

    if result.content[0].type == "image" or result.content[0].type == "audio":

        image_content = base64.b64decode(result.content[0].data)
        media_type = result.content[0].mimeType
        logging.debug(media_type)
        ext = mimetypes.guess_extension(media_type)
        logging.debug(ext)

        filename = f"{secrets.token_urlsafe(8)}{ext}"

        file_info = image_content, filename

        if result.content[0].type == "image":
            tool_image_results.append(file_info)
        else:
            tool_file_results.append(file_info)

        with open(os.path.join("downloads", filename), "wb") as f:
            f.write(image_content)

    else:
        tool_results.append({name: f"{result.data}"})


