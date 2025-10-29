import asyncio
import json
import logging
import re
from typing import List, Dict

from fastmcp import Client

from core.config import Config
from core.discord_messages import DiscordMessage, DiscordMessageReplyTmp, \
    DiscordMessageRemoveTmp, DiscordMessageReply, DiscordMessageReplyTmpError
from providers.base import BaseLLM, LLMToolCall
from providers.utils.chat import LLMChat
from providers.utils.error_reasoning import error_reasoning
from providers.utils.mcp_client_integrations.base import MCPIntegration
from providers.utils.response_filtering import filter_response
from providers.utils.tool_calls import mcp_to_dict_tools, get_custom_tools_system_prompt, get_tools_system_prompt


async def generate_with_mcp(llm: BaseLLM, chat: LLMChat, queue: asyncio.Queue[DiscordMessage | None], integration: MCPIntegration, use_help_bot: bool = False):

    if not Config.MCP_SERVER_URL:
        raise Exception("Kein MCP Server URL verfügbar")
    client = Client(Config.MCP_SERVER_URL, log_handler=integration.log_handler, progress_handler=integration.progress_handler)

    async with client:

        mcp_tools = await client.list_tools()

        mcp_tools = integration.filter_tool_list(mcp_tools)
        mcp_dict_tools = mcp_to_dict_tools(mcp_tools)

        logging.info(mcp_tools)
        logging.info(mcp_dict_tools)

        if not Config.TOOL_INTEGRATION:
            chat.system_entry["content"] += get_custom_tools_system_prompt(mcp_tools)
        else:
            chat.system_entry["content"] += get_tools_system_prompt()

        tool_call_errors = False


        for i in range(Config.MAX_TOOL_CALLS):

            logging.info(f"Tool Call Errors: {tool_call_errors}")

            deny_tools = Config.DENY_RECURSIVE_TOOL_CALLING and not tool_call_errors and i > 0

            use_integrated_tools = Config.TOOL_INTEGRATION and not deny_tools

            logging.info(f"Use integrated tools: {use_integrated_tools}")

            response = await llm.generate(chat, tools= mcp_to_dict_tools(mcp_tools) if use_integrated_tools else None)

            logging.info(f"RESPONSE: {response}")


            if response.text:

                chat.history.append({"role": "assistant", "content": response.text})
                await queue.put(DiscordMessageReply(value=filter_response(response.text, Config.OLLAMA_MODEL)))

            if deny_tools:
                break

            try:
                if Config.TOOL_INTEGRATION and response.tool_calls:
                    tool_calls = response.tool_calls
                else:
                    tool_calls = extract_custom_tool_calls(response.text)

                tool_call_errors = False

            except Exception as e:

                logging.exception(e, exc_info=True)

                if Config.HELP_DISCORD_ID and use_help_bot:
                    await queue.put(DiscordMessageReplyTmpError(
                        value=f"<@{Config.HELP_DISCORD_ID}> Ein Fehler ist aufgetreten: {e}",
                        embed=False
                    ))
                    break

                try:
                    await queue.put(DiscordMessageReplyTmp(
                        key="reasoning",
                        value="Aufgetretener Fehler wird analysiert..."
                    ))
                    reasoning = await error_reasoning(str(e), llm, chat)

                except Exception as f:
                    logging.error(f)
                    reasoning = str(e)

                finally:
                    await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                chat.history.append({"role": "user", "name": "system", "content": reasoning})
                tool_call_errors = True

                continue


            if tool_calls:

                run_again = False

                for tool_call in tool_calls:

                    logging.info(f"TOOL CALL: {tool_call}")

                    name = tool_call.name
                    arguments = tool_call.arguments


                    try:

                        formatted_args = "\n".join(f" - **{k}:** {v}" for k, v in arguments.items())
                        await queue.put(DiscordMessageReplyTmp(key=name, value=f"Das Tool **{name}** wird aufgerufen:\n{formatted_args}"))

                        result = await client.call_tool(name, arguments)



                        logging.info(f"Tool Call Result bekommen für {name}")

                        if not result.content:
                            logging.warning("Kein Tool Result Content, manuelle Unterbrechung")
                            continue # Manuelle Unterbrechung

                        else:

                            if use_integrated_tools:
                                chat.history.append(construct_tool_call_message([tool_call]))

                            run_again = await integration.process_tool_result(name, result, chat) or run_again

                    except Exception as e:
                        logging.exception(e, exc_info=True)

                        if Config.HELP_DISCORD_ID and use_help_bot:
                            await queue.put(DiscordMessageReplyTmpError(
                                value=f"<@{Config.HELP_DISCORD_ID}> Ein Fehler ist aufgetreten: {e}",
                                embed=False
                            ))
                            break

                        try:
                            await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Aufgetretener Fehler wird analysiert..."))
                            reasoning = await error_reasoning(str(e), llm, chat)

                        except Exception as f:
                            logging.error(f)
                            reasoning = str(e)

                        finally:
                            await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                        chat.history.append(construct_tool_call_results(name, reasoning))

                        tool_call_errors = True


                logging.info(chat.history)

                if not run_again:
                    logging.debug("Die Tool Results werden nicht erneut vom LLM verarbeitet")
                    break

            else:
                break


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

def construct_tool_call_message(tool_calls: List[LLMToolCall]) -> Dict[str, str]:

    return {"role": "system", "tool_calls": [
        {"id": t.name, "arguments": t.arguments} for t in tool_calls
    ]}

def construct_tool_call_results(name: str, content: str) -> Dict[str, str]: # TODO modularisieren zum Anpassen für verschiedene Modelle

    return {"role": "system", "id": name, "content": f"#{content}"}


