import asyncio
import base64
import json
import mimetypes
import os
import re
import secrets
import time
from collections.abc import Callable

import tiktoken
from fastmcp import Client
from fastmcp.client.logging import LogMessage
from mcp.server.fastmcp.exceptions import ToolError
from ollama import AsyncClient
from typing import List, Dict, Awaitable, Tuple

from mcp import Tool

import GPUtil

from discord_message import DiscordMessage, DiscordMessageTmp, DiscordMessageReply, DiscordMessageFile


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
    
{json.dumps(dict_tools, separators=(',', ':'))}

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

async def call_ai(history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage], channel: str):

    try:

        check_free_vram(required_gb=10)

        async def log_handler(message: LogMessage):
            print(f"EVENT: {message.data}")
            await queue.put(DiscordMessageTmp(str(message.data)))

        client = Client(os.getenv("MCP_SERVER_URL"), log_handler=log_handler,)

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

                response = await call_ollama(chat)

                tool_calls = extract_tool_calls(response)

                if tool_calls:

                    print(response)

                    await queue.put(DiscordMessageReply(response))

                    tool_results = []
                    tool_image_results = []

                    for tool_call in tool_calls:

                        print(f"TOOL CALL: {tool_call.get("name")}")

                        name = tool_call.get("name")
                        arguments = tool_call.get("arguments", {})


                        try:
                            result = await client.call_tool(name, arguments)

                            if result[0].type == "image":

                                image_content = base64.b64decode(result[0].data)
                                media_type = result[0].mimeType
                                ext = mimetypes.guess_extension(media_type)

                                filename = f"{secrets.token_urlsafe(8)}{ext}"

                                file_info = image_content, filename

                                tool_image_results.append(file_info)

                                with open(os.path.join("downloads", filename), "wb") as f:
                                    f.write(image_content)

                            else:
                                tool_results.append({name: json.loads(result[0].text)})

                        except ToolError as e:
                            time.sleep(7) #Damit VRAM ggf. wieder freigegeben wird
                            tool_results.append({name: str(e)})

                    chat.history.append({"role": "assistant", "content": response})

                    if tool_results:
                        tool_results_message = json.dumps({"tool_results": tool_results})

                        print(tool_results_message)

                        chat.history.append({"role": "system", "content": tool_results_message})

                    for image_content, filename in tool_image_results:
                        await queue.put(DiscordMessageFile(image_content, filename))
                        chat.history.append({"role": "assistant", "content": "", "images": [os.path.join("downloads", filename)]})


                    print(chat.history)

                    if not tool_results:
                        break

                else:
                    await queue.put(DiscordMessageReply(response))
                    break

    except Exception as e:
        print(e)
        await queue.put(DiscordMessageTmp(str(e)))


def extract_tool_calls(text: str) -> List[Dict]:
    tool_calls = []
    pattern = r'```tool(.*?)```'

    matches = re.findall(pattern, text, flags=re.DOTALL)
    for raw in matches:
        raw_json = raw.strip()
        try:
            tool_call_data = json.loads(raw_json)
            tool_calls.append(tool_call_data)
        except json.JSONDecodeError:
            continue  # Falls ungültig, wird einfach übersprungen

    return tool_calls


print("NEW OLLAMA CLIENT")
ollama_client = AsyncClient(host=os.getenv("OLLAMA_URL", "http://localhost:11434"))
ollama_lock = asyncio.Lock()


import pynvml

def check_free_vram(required_gb=8):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Nur GPU 0
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    free_gb = info.free / 1024**3
    if free_gb < required_gb:
        raise RuntimeError(f"Nicht genug VRAM: {free_gb:.2f} GB frei, {required_gb} GB benötigt")
    print(f"Genug VRAM vorhanden: {free_gb:.2f} GB frei")

async def call_ollama(chat: OllamaChat) -> str:

    model_name = os.getenv("GEMMA3_MODEL", "gemma3n:e4b")
    temperature = float(os.getenv("GEMMA3_MODEL_TEMPERATURE", 0.7))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    async with chat.lock:

        try:

            # Rufe das Modell auf
            response = await ollama_client.chat(
                model=model_name,
                messages=chat.history,
                stream=False,
                keep_alive=keep_alive,
                options={
                    'temperature': temperature
                }
            )

            return response['message']['content']

        except Exception as e:
            return f"Ollama Fehler: {str(e)}"

