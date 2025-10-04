import json
from typing import List, Dict

from fastmcp.tools import Tool


def mcp_to_dict_tools(mcp_tools: List[Tool]) -> List[Dict[str, str|Dict]]:

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


def get_custom_tools_system_prompt(mcp_tools: List[Tool]) -> str:

    dict_tools = mcp_to_dict_tools(mcp_tools)

    return f"""
Du bist hilfreich und zuverlässig.

**WAS DU KANNST**

*Du hast Zugriff auf folgende Tools:*

{json.dumps(dict_tools, separators=(',', ': '), ensure_ascii=False)}

Nutze die Tools, um Informationen zu erhalten und Aufgaben zu erledigen. Frage, wenn du dir unsicher bist. 
Nutze die Tools immer nur wenn nötig!
Wenn du gefragt wirst, was du kannst, listest du immer genau diese Tools auf!


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


def get_tools_system_prompt() -> str:

    return """

***Tool Calls***

Du hast eine Liste an Tools (Functions) die du verwenden kannst. Du bist Profi darin diese Tools zu verwenden.

💡 **Erklärung wie es funktioniert**
Wenn du Tools aufrufst werden die entsprechenden Funktionen aufgerufen.
Deren Ergebnisse (tool_results) werden dann temporär an den Nachrichtenverlauf als System Message angehängt und du wirst damit direkt nochmal aufgerufen.
Dann kannst du auf Basis der Ergebnisse dem User antworten. Der User bekommt die Ergebnisse nicht.

⚠️ **WICHTIG**
Rufe das Tool dann NIEMALS wieder erneut auf, da es sonst zu einer Endlosschleife kommt! Antworte stattdessen dem User basierend auf den Ergebnissen."""