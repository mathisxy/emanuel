import asyncio
import json
import os
import re
from collections.abc import Callable

from discord.ext.commands.core import hooked_wrapped_callback
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
    
    Für das beantworten von Fragen der User, zu der es ein passendes Tool gibt, nutzt du immer die Antworten von Tool-Calls. Du nutzt dafür keine vorherigen Chat-Informationen.
    
    Du hast Zugriff auf folgende Tools:
    


{json.dumps(dict_tools, indent=2)}


🔧 **Tools aufrufen**  

Sammle alle Tools die du aufrufen willst in einer Liste.

Verwende dann immer EXAKT dieses Format für die Tool-Calls:

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



📋 Regeln für Tool-Nutzung:
1. Verwende Tools nur wenn nötig
2. Verwende das EXAKTE Format für Tool-Calls
3. Fülle alle erforderlichen Parameter aus
4. Nach Tool-Calls, warte immer auf das Ergebnis bevor du antwortest


WICHTIG: Warte immer auf das Ergebnis des Tool-Calls, bevor du antwortest. Antworte nicht, bevor du die Ergebnisse der Tools erhalten hast.

"""

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


            while True:

                print(history)

                response = await call_ollama(history, f"{instructions}\n{system_prompt}")

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

                    tool_results_message = "\n".join(tool_results)

                    print(tool_results_message)

                    await reply_callback(cleaned_response.strip())

                    history = history + [
                        {"role": "assistant", "content": response},
                        {"role": "system", "content": f"{{'tool_results': [{tool_results_message}]}}"}
                    ]

                    print(history)

                else:
                    await reply_callback(response)
                    return


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
        cleaned_content = re.sub(pattern, '', content, flags=re.DOTALL).strip()
        cleaned_history.append({**message, "content": cleaned_content})

    return cleaned_history

ollama_client = AsyncClient(host=os.getenv("OLLAMA_URL", "http://localhost:11434"))
ollama_lock = asyncio.Lock()


async def call_ollama(history: List[Dict], instructions: str) -> str:

    #ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model_name = os.getenv("GEMMA3_MODEL", "gemma3n:e4b")
    temperature = float(os.getenv("GEMMA3_MODEL_TEMPERATURE", 0.7))

    # Baue den Prompt aus Historie und Instruktionen
    messages = [{"role": "system", "content": instructions}]
    messages.extend(history)

    async with ollama_lock:

        try:
            # Erstelle Ollama Client mit optionaler Host-Konfiguration
            #client = AsyncClient(host=ollama_url)

            # Rufe das Modell auf
            response = await ollama_client.chat(
                model=model_name,
                messages=messages,
                stream=False,
                keep_alive='10m',
                options={
                    'temperature': temperature
                }
            )

            return response['message']['content']

        except Exception as e:
            return f"Ollama Fehler: {str(e)}"

