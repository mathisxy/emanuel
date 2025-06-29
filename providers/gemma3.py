import os
import aiohttp
from typing import List, Dict

async def call_ai(history: List[Dict], instructions: str) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model_name = os.getenv("GEMMA3_MODEL", "gemma3n:e4b")

    # Baue den Prompt aus Historie und Instruktionen
    messages = [{"role": "system", "content": instructions}]
    messages.extend(history)

    # Ollama API Payload
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{ollama_url}/api/chat", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["message"]["content"]
                else:
                    return f"Ollama Fehler: {response.status} - {await response.text()}"
    except aiohttp.ClientError as e:
        return f"Verbindungsfehler zu Ollama: {str(e)}"
    except Exception as e:
        return f"Unbekannter Fehler: {str(e)}"