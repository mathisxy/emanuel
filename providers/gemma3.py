import asyncio
import json
import os
import re
from collections.abc import Callable

import tiktoken
from ollama import AsyncClient
from typing import List, Dict, Awaitable, Tuple

from mcp import ClientSession, Tool
from mcp.client.streamable_http import streamablehttp_client


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

    return f"""Du bist hilfreich.
Du machst keine zu langen Antworten.
Du hast Zugriff auf folgende Tools:
    
{json.dumps(dict_tools, separators=(',', ':'))}

Nutze die Tools, um Informationen zu erhalten und Aufgaben zu erledigen. Frage, wenn du dir unsicher bist. 
Nutze die Tools nur wenn nötig.


🔧 **Tools aufrufen**
Sammle als erstes ALLE Tools, die du verwenden willst.
Schreibe dann ALLE gesammelten Tool-Calls untereinander auf.
Verwende immer EXAKT dieses JSON-Format für die Tool-Calls:


||```tool
{{
  "name": "tool1",
  "arguments": {{
    "parameter1": "wert1"
  }}
}}
```||
||```tool
{{
  "name": "tool2",
  "arguments": {{}}
}}
```||
etc.
 
 
💡 **Erklärung wie es funktioniert**
Deine Antworten werden nach regex r'```tool(.*?)```' durchsucht.
Alle Treffer werden mit JSON geparst und dann aus der Antwort ausgeschnitten.
Falls es Treffer gibt, werden die entsprechenden Tools anhand der JSON-Objekte aufgerufen.
Die Ergebnisse werden dann temporär an den Nachrichtenverlauf angehängt und du wirst damit direkt nochmal aufgerufen.
Dann kannst du auf Basis der Ergebnisse dem User antworten. Der User bekommt die Ergebnisse nicht.
"""

#WICHTIG: Warte immer auf das Ergebnis der gesamten Tool-Calls, bevor du antwortest. Antworte nicht, wenn du noch keine Ergebnisse der Tools erhalten hast.

#Wenn du die Tool-Ergebnisse bekommen hast, antwortest du normal auf Basis der Ergebnisse.

#📋 Regeln für Tool-Nutzung:
#1. Verwende Tools immer dann wenn nötig
#2. Verwende das EXAKTE Format für Tool-Calls
#3. Fülle alle erforderlichen Parameter aus
#4. Nach den ganzen Tool-Calls warte immer auf das Ergebnis, bevor du antwortest


#Es ist wichtig, dass du:
#1. Immer zuerst die Tools nutzt, um Informationen zu bekommen. 🛠️
#2. Immer nur die Ergebnisse der Tools in deiner Antwort verwendest. 💬
#3. Dich nicht an ältere Nachrichten anlehnst, sondern immer "frisch" antwortest. 🆕


class OllamaChat:

    client: AsyncClient
    lock: asyncio.Lock
    history: List[Dict[str, str]]
    tokenizer: tiktoken

    max_tokens = 3700

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


ollama_chat = OllamaChat()

async def call_ai(history: List[Dict], instructions: str, reply_callback: Callable[[str], Awaitable[None]], channel: str):

    async with streamablehttp_client(os.getenv("MCP_SERVER_URL")) as (
            read_stream,
            write_stream,
            _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:

            try:

                # Initialize the connection
                await session.initialize()

                tools_response = await session.list_tools()
                mcp_tools = tools_response.tools

                system_prompt = get_tools_system_prompt(mcp_tools)

                #print(system_prompt)

                enc = tiktoken.get_encoding("cl100k_base")  # GPT-ähnlicher Tokenizer
                print(f"System Message Tokens: {len(enc.encode(system_prompt))}")

                ollama_chat.update_history(history, f"{instructions}\n\n{system_prompt}")

                print(ollama_chat.history)

                for i in range(7):

                    response = await call_ollama(ollama_chat)

                    tool_calls = extract_tool_calls(response)

                    if tool_calls:

                        print(response)

                        tool_results = []

                        for tool_call in tool_calls:

                            print(f"TOOL CALL: {tool_call.get("name")}")

                            name = tool_call.get("name")
                            arguments = tool_call.get("arguments", {})

                            result = await session.call_tool(name, arguments)
                            tool_results.append(f"{{'{name}': '{result.content[0].text}'}}")

                        tool_results_message = ",\n".join(tool_results)

                        print(tool_results_message)

                        await reply_callback(response)

                        ollama_chat.history = ollama_chat.history + [
                            {"role": "assistant", "content": response},
                            {"role": "system", "content": f"{{\"tool_results\": [{tool_results_message}]}}"}
                        ]

                        print(ollama_chat.history)

                    else:
                        await reply_callback(response)
                        break

            except Exception as e:
                await reply_callback(f"Fehler: {e}")


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

