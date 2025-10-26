import logging

from providers.utils.chat import LLMChat
from providers.utils.vram import wait_for_vram


async def error_reasoning(
        error_message: str,
        chat: LLMChat,
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

    reasoning_chat = LLMChat()
    reasoning_chat.lock = chat.lock
    reasoning_chat.history.append({"role": "system", "content": context})

    await wait_for_vram(required_gb=11)
    reasoning = await call_ollama(reasoning_chat)

    reasoning_content = reasoning.message.content

    logging.info(reasoning_content)

    return reasoning_content