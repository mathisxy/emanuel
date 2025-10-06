import asyncio
import base64
import json
import mimetypes
import os
import re
import secrets
import time
from typing import List, Dict, Literal

import GPUtil
import fastmcp
import tiktoken
from fastmcp import Client
from fastmcp.client.logging import LogMessage
from mcp import Tool
from ollama import AsyncClient, ChatResponse, embed
import logging

from discord_message import DiscordMessage, DiscordMessageReply, DiscordMessageFile, \
    DiscordMessageReplyTmp, DiscordMessageProgressTmp, DiscordMessageFileTmp, DiscordMessageRemoveTmp

from providers.ollama_tool_calls import mcp_to_dict_tools, get_custom_tools_system_prompt, get_tools_system_prompt


class OllamaChat:

    client: AsyncClient
    lock: asyncio.Lock
    history: List[Dict[str, str]]
    tokenizer: tiktoken

    max_tokens = 3700 if len(GPUtil.getGPUs()) == 0 else int(os.getenv("MAX_TOKENS", 64000))
    print(f"MAX TOKENS: {max_tokens}")

    def __init__(self):

        self.client = AsyncClient(host=os.getenv("OLLAMA_URL", "http://localhost:11434"))
        self.lock = asyncio.Lock()
        self.history = []
        self.tokenizer = tiktoken.get_encoding("cl100k_base")


    def update_history(self, new_history: List[Dict[str, str]], instructions_entry: Dict[str, str], min_overlap=1):

        history_without_tool_results = [x for x in self.history if not (x["role"] == "system" and x["content"].startswith('#'))]

        #print("HISTORY WITHOUT TOOLS")
        #print(history_without_tool_results)
        #print(new_history)

        max_overlap_length = len(history_without_tool_results)
        overlap_length = None

        for length in range(max_overlap_length, min_overlap, -1):
            if history_without_tool_results[-length:] == new_history[:length]:
                overlap_length = length
                logging.info(f"OVERLAP LENGTH: {overlap_length}")
                break

        if not overlap_length:
            logging.info("KEIN OVERLAP")
            print(self.history)
            print(new_history)
            self.history = [instructions_entry]
            self.history.extend(new_history)
        elif self.history[0] == instructions_entry:
            self.history = self.history + new_history[overlap_length:]
        else:
            print("NEW INSTRUCTIONS")
            print(self.history[0])
            print(instructions_entry)
            self.history = [instructions_entry]
            self.history.extend(new_history)

        print(self.count_tokens())

        if self.count_tokens() > self.max_tokens:
            print("CUTTING")
            self.history = new_history


    def build_prompt(self, history=None) -> str:
        if history is None:
            history = self.history

        prompt_lines = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_lines.append(f"{role}: {content}")
        return "\n".join(prompt_lines)

    def count_tokens(self, history=None) -> int:
        prompt = self.build_prompt(history)
        return len(self.tokenizer.encode(prompt))


ollama_chat: Dict[str, OllamaChat] = {}


async def call_ai(history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage|None], channel: str):

    try:

        async def log_handler(message: fastmcp.client.logging.LogMessage):
            if message.data.get("msg") == "preview_image":
                image_base64 = message.data.get("extra").get("base64")
                image_type = message.data.get("extra").get("type")
                image_bytes = base64.b64decode(image_base64)
                await queue.put(DiscordMessageFileTmp(value=image_bytes, filename=f"preview.{image_type}", key="progress"))
            else:
                print(f"EVENT: {message.data}")
                await queue.put(DiscordMessageReplyTmp(value=str(message.data.get("msg")), key=message.level.lower()))
        async def progress_handler(progress: float, total: float|None, message: str|None):
            print(f"PROGRESS: {progress}/{total}:{message}")
            await queue.put(DiscordMessageProgressTmp(progress=progress, total=total, key="progress"))

        client = Client(os.getenv("MCP_SERVER_URL"), log_handler=log_handler, progress_handler=progress_handler)

        async with client:

            chat = ollama_chat.setdefault(channel, OllamaChat())

            mcp_tools = await client.list_tools()

            mcp_tools = filter_tool_list(mcp_tools)
            mcp_dict_tools = mcp_to_dict_tools(mcp_tools)

            logging.info(mcp_tools)
            logging.info(mcp_dict_tools)

            has_tool_integration = os.getenv("TOOL_INTEGRATION", "").lower() == "true"

            system_prompt = instructions

            if not has_tool_integration:
                system_prompt += get_custom_tools_system_prompt(mcp_tools, language=os.getenv("LANGUAGE", "de"))
            else:
                system_prompt += get_tools_system_prompt(language=os.getenv("LANGUAGE", "de"))

            logging.debug(f"SYSTEM PROMPT: {system_prompt}")

            enc = tiktoken.get_encoding("cl100k_base")  # GPT-ähnlicher Tokenizer
            logging.info(f"System Message Tokens: {len(enc.encode(system_prompt))}")

            instructions = {"role": "system", "content": system_prompt}

            chat.update_history(history, instructions)

            logging.debug(f"HISTORY: {chat.history}")

            tool_call_errors = False

            for i in range(int(os.getenv("MAX_TOOL_CALLS", 7))):

                logging.info(f"Tool Call Errors: {tool_call_errors}")

                await wait_for_vram(required_gb=11)

                deny_tools = os.getenv("DENY_RECURSIVE_TOOL_CALLING", "").lower() == "true" and not tool_call_errors and i > 0

                use_integrated_tools = has_tool_integration and not deny_tools

                logging.info(f"Use integrated tools: {use_integrated_tools}")

                response = await call_ollama(chat, tools= mcp_to_dict_tools(mcp_tools) if use_integrated_tools else None)

                if response.message.content:

                    chat.history.append({"role": "assistant", "content": response.message.content})
                    await queue.put(DiscordMessageReply(response.message.content))

                if deny_tools:
                    break

                try:
                    if has_tool_integration and response.message.tool_calls:
                        tool_calls = [{"name": t.function.name, "arguments": t.function.arguments} for t in response.message.tool_calls]
                    else:
                        tool_calls = extract_custom_tool_calls(response.message.content)

                    tool_call_errors = False

                except Exception as e:

                    logging.error(e)

                    if os.getenv("HELP_DISCORD_ID"):
                        await queue.put(DiscordMessageReplyTmp("error", f"<@{os.getenv("HELP_DISCORD_ID")}> Ein Fehler ist aufgetreten: {e}", embed=False))
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

                        name = tool_call.get("name")
                        arguments = tool_call.get("arguments", {})


                        try:

                            await queue.put(DiscordMessageReplyTmp(name, f"Das Tool {name} wird aufgerufen: {arguments}"))

                            result = await client.call_tool(name, arguments)

                            logging.info(f"Tool Call Result bekommen für {name}")

                            if result.content is None:
                                logging.warning("Kein Tool Result Content, manuelle Unterbrechung")
                                break # Manuelle Unterbrechung

                            else:

                                if use_integrated_tools:
                                    chat.history.append({"role": "assistant", "content": f"#<function_call>{tool_call}</function_call>"})

                                process_tool_result(name, result, tool_results, tool_image_results, tool_file_results)

                        except Exception as e:
                            print(f"TOOL: {name} ERROR: {e}")
                            logging.error(e)

                            if os.getenv("HELP_DISCORD_ID"):
                                await queue.put(DiscordMessageReplyTmp("error", f"<@{os.getenv("HELP_DISCORD_ID")}> Ein Fehler ist aufgetreten: {e}", embed=False))
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

    except Exception as e:
        print(f"KEIN TOOLERROR: {e}")
        logging.error(e)
        await queue.put(DiscordMessageReplyTmp(value=str(e), key="error"))

def filter_tool_list(tools: List[Tool]):

    return [
        tool for tool in tools
        if hasattr(tool, 'meta') and tool.meta and
           tool.meta.get('_fastmcp', {}) and
           os.getenv("NAME") in tool.meta.get('_fastmcp', {}).get('tags', [])
    ]


def extract_custom_tool_calls(text: str) -> List[Dict]:
    tool_calls = []
    pattern = r'```tool(.*?)```'

    matches = re.findall(pattern, text, flags=re.DOTALL)
    for raw in matches:
        raw_json = raw.strip()
        try:
            tool_call_data = json.loads(raw_json)
            tool_calls.append(tool_call_data)
        except json.JSONDecodeError as e:
            raise Exception(f"Fehler beim JSON Dekodieren des Tool Calls: {e}")

    return tool_calls

def process_tool_result(name: str, result: fastmcp.client.client.CallToolResult, tool_results: List, tool_image_results: List, tool_file_results: List):

    logging.info(result.content[0].type)

    if result.content[0].type == "text":
        logging.info(result.content[0].text)

    if result.content[0].type == "image" or result.content[0].type == "audio":

        image_content = base64.b64decode(result.content[0].data)
        media_type = result.content[0].mimeType
        print(media_type)
        ext = mimetypes.guess_extension(media_type)
        print(ext)

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

import pynvml

def check_free_vram(required_gb:float=8):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Nur GPU 0
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    free_gb = info.free / 1024**3
    if free_gb < required_gb:
        raise RuntimeError(f"Nicht genug VRAM: {free_gb:.2f} GB frei, {required_gb} GB benötigt")
    print(f"Genug VRAM vorhanden: {free_gb:.2f} GB frei")

async def wait_for_vram(required_gb:float=8, timeout:float=20, interval:float=1):

    start = time.time()

    while True:
        try:
            check_free_vram(required_gb=required_gb)
            break
        except RuntimeError as e:
            if (time.time() - start) >= timeout:
                raise TimeoutError(f"Timeout: {e}")
            else:
                await asyncio.sleep(interval)

async def call_ollama(chat: OllamaChat, model_name: str|None = None, temperature: str|None = None, think:bool|Literal["low", "medium", "high"]|None = None, tools: List[Dict]|None = None,  keep_alive: str|None = None, timeout: float|None = None) -> ChatResponse:

    model_name = model_name if model_name else os.getenv("GEMMA3_MODEL", "gemma3n:e4b")
    temperature = temperature if temperature else float(os.getenv("GEMMA3_MODEL_TEMPERATURE", 0.7))
    think = think if think else os.getenv("THINK", None)
    keep_alive = keep_alive if keep_alive else os.getenv("OLLAMA_KEEP_ALIVE", "10m")
    timeout = timeout if timeout else os.getenv("OLLAMA_TIMEOUT", None)
    timeout = float(timeout)

    async with chat.lock:

        try:

            # Rufe das Modell auf
            response = await asyncio.wait_for(
                chat.client.chat(
                    model=model_name,
                    messages=chat.history,
                    stream=False,
                    keep_alive=keep_alive,
                    options={
                        'temperature': temperature,
                    },
                    **({"think": think} if think is not None else {}),
                    **({"tools": tools} if tools is not None else {}),
                ),
                timeout=timeout,
            )

            logging.info(response)

            return response # ['message']['content']

        except Exception as e:
            logging.error(e)
            raise Exception(f"Ollama Fehler: {e}")
        


async def error_reasoning(
        error_message: str,
        chat: OllamaChat,
):

    instructions = chat.history[0].get("content")
    assistant_messages = []
    user_message = ""

    for message in reversed(chat.history):

        logging.info(message)

        if message.get("role") == "user":
            logging.info("ist user message -> break")
            user_message = message.get("content")
            break

        assistant_messages.insert(0, message.get("content"))

    # Formatierung

    context = f"""
***DEINE AUFGABE***
Du hilfst einem KI Assistenten (Gemma3 12B) einen Fehler zu beheben.
Als Überblick bekommst du:
 - die Instruktionen, die dieser Assistent bekommen hat
 - die letzten relevanten Nachrichten
 - die Fehlermeldung

Erwähne zuerst einmal welcher Fehler aufgetreten ist.
Erkläre dann klar und möglichst knapp wie der Fehler entstanden ist und wie er behoben werden kann.


***Instruktionen für den Assistenten***

\"{instructions}\"


***Letzte Nachricht des Nutzers***

\"{user_message}\"


***Darauffolgende Nachrichten des Assistenten***

\"{"\n---\n".join(assistant_messages)}\"


***Die Fehlermeldung***

\"{error_message}\"
"""

    logging.info(context)

    reasoning_chat = OllamaChat()
    reasoning_chat.lock = chat.lock
    reasoning_chat.history.append({"role": "system", "content": context})

    await wait_for_vram(required_gb=11)
    reasoning = await call_ollama(reasoning_chat, model_name="gpt-oss:20b", think="low", timeout=360)

    reasoning_content = reasoning.message.content

    logging.info(reasoning_content)

    return reasoning_content


