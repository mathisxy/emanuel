import json
import os
import re

from ollama import AsyncClient
from typing import List, Dict

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

    return f"""Du bist ein hilfreicher Assistent mit Zugang zu folgenden Tools:

{json.dumps(dict_tools)}

WICHTIG: Wenn du ein Tool verwenden möchtest, antworte EXAKT in diesem Format:

<TOOL_CALL>
{{
  "name": "tool_name",
  "arguments": {{
    "parameter1": "wert1",
    "parameter2": "wert2"
  }}
}}
</TOOL_CALL>

Nach einem Tool-Aufruf wirst du das Ergebnis erhalten und kannst normal antworten.

Regeln:
1. Verwende Tools nur wenn nötig
2. Verwende das EXAKTE Format für Tool-Calls
3. Fülle alle erforderlichen Parameter aus
4. Nach dem Tool-Call, warte auf das Ergebnis bevor du antwortest
"""

async def call_ai(history: List[Dict], instructions: str) -> str:

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

                tool_calls = extract_tool_calls(response)

                if tool_calls:

                    tool_results = []

                    for tool_call in tool_calls:

                        name = tool_call.get("name")
                        arguments = tool_call.get("arguments", {})

                        result = await session.call_tool(name, arguments)
                        tool_results.append(f"Tool {name} Ergebnis: {result.content}")

                    tool_results_message = "\n\n".join(tool_results)

                    history = history + [
                        {"role": "assistant", "content": f"Nur du kannst das sehen: {response}"},
                        {"role": "user", "content": f"Hier sind die Toolergebnisse, nur du kannst sie sehen: {tool_results_message}"}
                    ]

                else:
                    return response


def extract_tool_calls(text: str) -> List[Dict]:

    tool_calls = []

    pattern = r'<TOOL_CALL>(.*?)</TOOL_CALL>'
    matches = re.findall(pattern, text, re.DOTALL)

    for match in matches:
        try:
            # Parse das JSON
            tool_call_data = json.loads(match.strip())
            tool_calls.append(tool_call_data)
        except json.JSONDecodeError as e:
            print(f"Fehler beim Parsen des Tool-Calls: {e}")
            continue

    return tool_calls

async def call_ollama(history: List[Dict], instructions: str) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model_name = os.getenv("GEMMA3_MODEL", "gemma3n:e4b")

    # Baue den Prompt aus Historie und Instruktionen
    messages = [{"role": "system", "content": instructions}]
    messages.extend(history)

    try:
        # Erstelle Ollama Client mit optionaler Host-Konfiguration
        client = AsyncClient(host=ollama_url)

        # Rufe das Modell auf
        response = await client.chat(
            model=model_name,
            messages=messages,
            stream=False,
            keep_alive='10m'
        )

        return response['message']['content']

    except Exception as e:
        return f"Ollama Fehler: {str(e)}"

