import json
from typing import List, Dict

from fastmcp.tools import Tool

from core.config import Config


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

    match Config.LANGUAGE:
        case "de":
            return f"""
Du bist hilfreich und zuverlässig.

**WAS DU KANNST**

*Du hast Zugriff auf folgende Tools:*

{json.dumps(dict_tools, separators=(',', ': '), ensure_ascii=False)}

Nutze die Tools, um Informationen zu erhalten und Aufgaben zu erledigen. Frage, wenn du dir unsicher bist. 
Nutze die Tools immer nur wenn nötig!
Wenn du gefragt wirst, was du kannst, listest du immer genau diese Tools auf!

Du nutzt immer EXAKT den Namen und die Argumente der Tool-Call Beschreibungen!


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
Dann antwortest du immer auf Basis der Ergebnisse dem User noch einmal. Der User bekommt die Ergebnisse nicht.

"""

        case "en":
            return f"""
You are helpful and reliable.

**WHAT YOU CAN DO**

*You have access to the following tools:*

{json.dumps(dict_tools, separators=(',', ': '), ensure_ascii=False)}

Use these tools to get information and complete tasks.
Ask if you're unsure.  
Only use the tools when necessary!  
If you are asked what you can do, always list exactly these tools!

You always use EXACTLY the name and arguments of the tool call descriptions!


🔧 **Calling Tools**
Always use EXACTLY this JSON format for tool calls:

||```tool
{{
  "name": "tool1",
  "arguments": {{
    "parameter1": "value1"
  }}
}}
```||

💡 **How it works**
Your responses are searched using the regex `r'```tool(.*?)```'`.  
All matches are parsed as JSON and then removed from the response.  
If matches are found, the corresponding tools are executed based on the JSON objects.  
The results are temporarily attached to the message history, and you are called again with them.  
You can then respond to the user based on those results. The user does not see the raw results.

"""
        case _:
            raise TypeError(f"Invalid Language: {Config.LANGUAGE}")


def get_tools_system_prompt() -> str:

    match Config.LANGUAGE:
        case "de":
            return """

***Tool Calls***

Du hast eine Liste an Tools (Functions) die du verwenden kannst. Du bist Profi darin diese Tools zu verwenden.

💡 **Erklärung wie es funktioniert**
Wenn du Tools aufrufst werden die entsprechenden Funktionen aufgerufen.
Deren Ergebnisse (tool_results) werden dann temporär an den Nachrichtenverlauf als System Message angehängt und du wirst damit direkt nochmal aufgerufen.
Dann kannst du auf Basis der Ergebnisse dem User antworten. Der User bekommt die Ergebnisse nicht.

⚠️ **WICHTIG**
Rufe das Tool dann NIEMALS wieder erneut auf, da es sonst zu einer Endlosschleife kommt! Antworte stattdessen dem User basierend auf den Ergebnissen.

"""

        case "en":
            return """
***Tool Calls***

You have a list of tools (functions) that you can use. You are an expert at using these tools.

💡 **How it works**  
When you call a tool, the corresponding function is executed.  
Its results (`tool_results`) are then temporarily attached to the message history as a system message, and you are immediately called again with them.  
You can then respond to the user based on these results. The user does not see the raw results.

⚠️ **IMPORTANT**  
Never call the tool again after receiving its results — otherwise, it will cause an infinite loop!  
Instead, respond to the user based on the results.

"""
        case _:
            raise TypeError(f"Invalid Language: {Config.LANGUAGE}")