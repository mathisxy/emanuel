import importlib
import io
from enum import Enum
from typing import List, Dict

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from mistralai import Mistral
from mistralai.extra.mcp.sse import MCPClientSSE, SSEServerParams
from mistralai.extra.run.context import RunContext

load_dotenv()

api_key = os.getenv("API_KEY")
model = os.getenv("MODEL")
discord_token = os.getenv("DISCORD_TOKEN")
mcp_server_url = os.getenv("MCP_SERVER_URL")
ai=os.getenv("AI", "mistral")

client = Mistral(api_key=api_key)

intents = discord.Intents.default()
intents.message_content = True  # Für Textnachrichten lesen
intents.messages = True  # explizit hinzufügen
bot = commands.Bot(command_prefix="!", intents=intents)


async def call_ai(history: List[Dict], instructions: str, provider: str) -> str:
    """Lädt dynamisch den AI-Provider und ruft ihn auf"""
    try:
        # Importiere das Modul basierend auf dem Provider-Namen
        module = importlib.import_module(f"providers.{provider}")
        # Rufe die call_ai Funktion des Moduls auf
        return await module.call_ai(history, instructions)
    except ImportError:
        return f"AI-Provider '{provider}' nicht gefunden!"
    except Exception as e:
        return f"Fehler beim AI-Aufruf: {str(e)}"


async def handle_message(message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions:

        async with message.channel.typing():

            history = []
            async for msg in message.channel.history(limit=20, oldest_first=False):

                if not msg.author == bot.user and not bot.user in msg.mentions:
                    continue

                role = "user" if msg.author != bot.user else "assistant"
                content = msg.clean_content

                if not content and msg.attachments:
                    author = "dir" if msg.author == bot.user else msg.author
                    content = f"Eine Datei wurde gesendet von {author}: {msg.attachments[0].filename}"

                if content:
                    history.append({"role": role, "content": content})

            history.reverse()
            print(history)

            reply = await call_ai(history, "Du bist Manuel, ein Discord Bot", ai)
            print(reply)
            if len(reply) > 2000:
                file = discord.File(io.BytesIO(reply.encode('utf-8')), filename=f"{bot.user.name}s Antwort.txt")
                await message.reply(file=file)
            else:
                await message.reply(reply)


@bot.event
async def on_message(message: discord.Message):
    await handle_message(message)




bot.run(discord_token)