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


🔧 **Tools aufrufen**
Sammle als erstes ALLE Tools, die du verwenden willst.
Schreibe dann ALLE gesammelten Tool-Calls untereinander auf.
Verwende immer EXAKT dieses JSON-Format für die Tool-Calls:

```tool
{{
  "name": "tool1",
  "arguments": {{
    "parameter1": "wert1"
  }}
}}
```
```tool
{{
  "name": "tool2",
  "arguments": {{}}
}}
```
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


async def call_ai(history: List[Dict], instructions: str, reply_callback: Callable[[str], Awaitable[None]]):

    async with streamablehttp_client(os.getenv("MCP_SERVER_URL")) as (
            read_stream,
            write_stream,
            _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection

            await session.initialize()

            tools_response = await session.list_tools()
            mcp_tools = tools_response.tools

            system_prompt = get_tools_system_prompt(mcp_tools)

            print(system_prompt)

            history = remove_tool_placeholders_from_history(history)

            enc = tiktoken.get_encoding("cl100k_base")  # GPT-ähnlicher Tokenizer
            print(f"System Message Tokens: {len(enc.encode(system_prompt))}")

            for i in range(7):

                print(history)

                response = await call_ollama(history, f"{instructions}\n\n{system_prompt}")

                tool_calls, cleaned_response = extract_tool_calls(response)

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

                    await reply_callback(cleaned_response.strip())

                    history = history + [
                        {"role": "assistant", "content": response},
                        {"role": "system", "content": f"{{'tool_results': [{tool_results_message}]}}"}
                    ]

                    print(history)

                else:
                    await reply_callback(response)
                    break


def extract_tool_calls(text: str) -> Tuple[List[Dict], str]:
    tool_calls = []

    pattern = r'```tool(.*?)```'

    def replace_match(match_obj):
        raw_json = match_obj.group(1).strip()
        try:
            tool_call_data = json.loads(raw_json)
            tool_calls.append(tool_call_data)
            tool_name = tool_call_data.get("name", "Unbekanntes Tool")
        except json.JSONDecodeError:
            tool_name = "Ungültiges Tool"
        return f"```🔧 {tool_name}```"

    cleaned_response = re.sub(pattern, replace_match, text, flags=re.DOTALL)

    return tool_calls, cleaned_response


def remove_tool_placeholders_from_history(history: List[Dict]) -> List[Dict]:
    pattern = r'```🔧.*?```'
    cleaned_history = []

    for message in history:
        content = message.get("content", "")
        # Entferne alle vorkommenden Tool-Platzhalter im content
        replacement = "> Hier stand ein valider Tool-Call"
        cleaned_content = re.sub(pattern, replacement, content, flags=re.DOTALL).strip()
        cleaned_history.append({**message, "content": cleaned_content})

    return cleaned_history

print("NEW OLLAMA CLIENT")
ollama_client = AsyncClient(host=os.getenv("OLLAMA_URL", "http://localhost:11434"))
ollama_lock = asyncio.Lock()


async def call_ollama(history: List[Dict], instructions: str) -> str:

    model_name = os.getenv("GEMMA3_MODEL", "gemma3n:e4b")
    temperature = float(os.getenv("GEMMA3_MODEL_TEMPERATURE", 0.7))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    # Baue den Prompt aus Historie und Instruktionen
    messages = [{"role": "system", "content": instructions}]
    messages.extend(history)

    async with ollama_lock:

        try:

            # Rufe das Modell auf
            response = await ollama_client.chat(
                model=model_name,
                messages=messages, #[{"role": "user", "content": "test"}],
                stream=False,
                keep_alive=keep_alive,
                options={
                    'temperature': temperature
                }
            )

            return response['message']['content']

        except Exception as e:
            return f"Ollama Fehler: {str(e)}"

