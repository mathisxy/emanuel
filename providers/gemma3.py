import asyncio
import base64
import json
import mimetypes
import os
import re
import secrets
import time
from typing import List, Dict

import GPUtil
import fastmcp
import tiktoken
from fastmcp import Client
from fastmcp.client.logging import LogMessage
from mcp import Tool
from ollama import AsyncClient
import logging

from torch.optim.optimizer import required

from discord_message import DiscordMessage, DiscordMessageReply, DiscordMessageFile, \
    DiscordMessageReplyTmp, DiscordMessageProgressTmp, DiscordMessageFileTmp, DiscordMessageRemoveTmp

logging.basicConfig(filename="bot.log", level=logging.INFO)

def mcp_to_dict_tools(mcp_tools: List[Tool]) -> List[Dict]:

    dict_tools = []

    for tool in mcp_tools:
        dict_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            }
        })

    return dict_tools

def get_tools_system_prompt(mcp_tools: List[Tool]) -> str:

    dict_tools = mcp_to_dict_tools(mcp_tools)

    return f"""Du bist hilfreich und zuverlässig.
Du machst keine zu langen Antworten.
Du hast Zugriff auf folgende Tools:
    
{json.dumps(dict_tools, indent=0, separators=(',', ': '), ensure_ascii=False)}

Nutze die Tools, um Informationen zu erhalten und Aufgaben zu erledigen. Frage, wenn du dir unsicher bist. 
Nutze die Tools immer nur wenn nötig!


🔧 **Tools aufrufen**
Verwende immer EXAKT dieses JSON-Format für die Tool-Calls:


||```tool
{{
  "name": "tool1",
  "arguments": {{
    "parameter1": "wert1"
  }}
}}
```||
 
 
💡 **Erklärung wie es funktioniert**
Deine Antworten werden nach regex r'```tool(.*?)```' durchsucht.
Alle Treffer werden mit JSON geparst und dann aus der Antwort ausgeschnitten.
Falls es Treffer gibt, werden die entsprechenden Tools anhand der JSON-Objekte aufgerufen.
Die Ergebnisse werden dann temporär an den Nachrichtenverlauf angehängt und du wirst damit direkt nochmal aufgerufen.
Dann kannst du auf Basis der Ergebnisse dem User antworten. Der User bekommt die Ergebnisse nicht.
"""


class OllamaChat:

    client: AsyncClient
    lock: asyncio.Lock
    history: List[Dict[str, str]]
    tokenizer: tiktoken

    max_tokens = 3700 if len(GPUtil.getGPUs()) == 0 else 64000
    print(f"MAX TOKENS: {max_tokens}")

    def __init__(self):

        self.client = AsyncClient(host=os.getenv("OLLAMA_URL", "http://localhost:11434"))
        self.lock = asyncio.Lock()
        self.history = []
        self.tokenizer = tiktoken.get_encoding("cl100k_base")


    def update_history(self, new_history: List[Dict[str, str]], instructions: str, min_overlap=1):

        history_without_tool_results = [x for x in self.history if not (x["role"] == "system" and x["content"].startswith('{"tool_results":'))]

        print("HISTORY WITHOUT TOOLS")
        print(history_without_tool_results)
        print(new_history)

        max_overlap_length = min(len(history_without_tool_results), len(new_history))
        overlap_length = None

        for length in range(max_overlap_length, min_overlap, -1):
            if history_without_tool_results[-length:] == new_history[:length]:
                overlap_length = length
                break

        if not overlap_length:
            print("KEIN OVERLAP")
            print(self.history)
            print(new_history)
            self.history = [{"role": "system", "content": instructions}]
            self.history.extend(new_history)
        elif self.history[0] == {"role": "system", "content": instructions}:
            self.history = self.history + new_history[overlap_length:]
        else:
            print("NEW INSTRUCTIONS")
            print(self.history[0])
            print({"role": "system", "content": instructions})
            self.history = [{"role": "system", "content": instructions}]
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

            system_prompt = get_tools_system_prompt(mcp_tools)

            #print(system_prompt)

            enc = tiktoken.get_encoding("cl100k_base")  # GPT-ähnlicher Tokenizer
            print(f"System Message Tokens: {len(enc.encode(system_prompt))}")

            chat.update_history(history, f"{instructions}\n\n{system_prompt}")

            print(chat.history)

            for i in range(int(os.getenv("MAX_TOOL_CALLS", 7))):

                await wait_for_vram(required_gb=11)

                response = await call_ollama(chat)

                chat.history.append({"role": "assistant", "content": response})


                try:
                    tool_calls = extract_tool_calls(response)
                except Exception as e:
                    await queue.put(DiscordMessageReply(response))

                    logging.error(e)

                    try:
                        await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Aufgetretener Fehler wird analysiert..."))
                        reasoning = await error_reasoning(str(e), chat)

                    except Exception as e:
                        logging.error(e)
                        #await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Analysieren des Fehlers fehlgeschlagen"))
                        reasoning = str(e)

                    finally:
                        await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                    chat.history.append({"role": "system", "content": reasoning})

                    continue


                if tool_calls:

                    print(response)

                    await queue.put(DiscordMessageReply(response))

                    tool_results = []
                    tool_image_results = []
                    tool_file_results = []

                    for tool_call in tool_calls:

                        print(f"TOOL CALL: {tool_call.get("name")}")

                        name = tool_call.get("name")
                        arguments = tool_call.get("arguments", {})


                        try:
                            result = await client.call_tool(name, arguments)

                            logging.info(f"Tool Call Result bekommen für {name}")

                            if not result.content:
                                break # Manuelle Unterbrechung

                            else:
                                logging.info(result.content[0].type)

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

                        except Exception as e:
                            print(f"TOOL: {name} ERROR: {e}")
                            logging.error(e)

                            try:
                                await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Aufgetretener Fehler wird analysiert..."))
                                reasoning = await error_reasoning(str(e), chat)

                            except Exception:
                                await queue.put(DiscordMessageReplyTmp(key="reasoning", value="Analysieren des Fehlers fehlgeschlagen"))
                                reasoning = str(e)

                            finally:
                                await queue.put(DiscordMessageRemoveTmp(key="reasoning"))

                            tool_results.append({name: reasoning})


                    if tool_results:
                        tool_results_message = json.dumps({"tool_results": tool_results})

                        print(tool_results_message)

                        chat.history.append({"role": "system", "content": tool_results_message})

                    for image_content, filename in tool_image_results:
                        await queue.put(DiscordMessageFile(image_content, filename))
                        chat.history.append({"role": "assistant", "content": "", "images": [os.path.join("downloads", filename)]})

                    for file_content, filename in tool_file_results:
                        await queue.put(DiscordMessageFile(file_content, filename))
                        chat.history.append({"role": "assistant", "content": f"Du hast eine Datei gesendet: {filename}"})


                    print(chat.history)

                    if not tool_results:
                        break

                else:
                    await queue.put(DiscordMessageReply(response))
                    break

    except Exception as e:
        print(f"KEIN TOOLERROR: {e}")
        logging.error(e)
        await queue.put(DiscordMessageReplyTmp(value=str(e), key="error"))


def extract_tool_calls(text: str) -> List[Dict]:
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


import pynvml

def check_free_vram(required_gb:float=8):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Nur GPU 0
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    free_gb = info.free / 1024**3
    if free_gb < required_gb:
        raise RuntimeError(f"Nicht genug VRAM: {free_gb:.2f} GB frei, {required_gb} GB benötigt")
    print(f"Genug VRAM vorhanden: {free_gb:.2f} GB frei")

async def wait_for_vram(required_gb:float=8, timeout:float=10, interval:float=1):

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

async def call_ollama(chat: OllamaChat, model_name: str|None = None, temperature: str|None = None, keep_alive: str|None = None) -> str:

    model_name = model_name if model_name else os.getenv("GEMMA3_MODEL", "gemma3n:e4b")
    temperature = temperature if temperature else float(os.getenv("GEMMA3_MODEL_TEMPERATURE", 0.7))
    keep_alive = keep_alive if keep_alive else os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    async with chat.lock:

        try:

            # Rufe das Modell auf
            response = await chat.client.chat(
                model=model_name,
                messages=chat.history,
                stream=False,
                keep_alive=keep_alive,
                options={
                    'temperature': temperature
                }
            )

            logging.info(response)

            return response['message']['content']

        except Exception as e:
            return f"Ollama Fehler: {str(e)}"
        


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
Zeige am besten auch ein Beispiel dafür wie es richtig geht.


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
    reasoning = await call_ollama(reasoning_chat, model_name="gpt-oss:20b")

    logging.info(reasoning)

    return reasoning


