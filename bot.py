import importlib
import io
from typing import List, Dict

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("API_KEY")
model = os.getenv("MODEL")
discord_token = os.getenv("DISCORD_TOKEN")
mcp_server_url = os.getenv("MCP_SERVER_URL")
ai=os.getenv("AI", "mistral")

intents = discord.Intents.default()
intents.message_content = True  # Für Textnachrichten lesen
intents.messages = True  # explizit hinzufügen
bot = commands.Bot(command_prefix="!", intents=intents)


module = importlib.import_module(f"providers.{ai}")


async def call_ai(history: List[Dict], instructions: str, reply_callback) -> str:
    try:
        return await module.call_ai(history, instructions, reply_callback)
    except Exception as e:
        return f"Fehler beim AI-Aufruf: {str(e)}"


def is_relevant_message(message: discord.Message) -> bool:
    return bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)


async def handle_message(message):
    if message.author == bot.user:
        return

    if is_relevant_message(message):

        async with message.channel.typing():

            async def reply_callback(reply: str):
                reply = reply.strip()
                print(f"REPLY: {reply}")
                if not reply:
                    return
                if len(reply) > 2000:
                    file = discord.File(io.BytesIO(reply.encode('utf-8')), filename=f"{bot.user.name}s Antwort.txt")
                    await message.channel.send(file=file)
                else:
                    await message.channel.send(reply)


            history = []
            max_count = int(os.getenv("MAX_MESSAGE_COUNT", 3))
            async for msg in message.channel.history(limit=20, oldest_first=False):

                if len(history) >= max_count:
                    break

                if msg.author != bot.user and not is_relevant_message(msg):
                    continue

                content = msg.clean_content

                if not content and msg.attachments:
                    author = "dir" if msg.author == bot.user else msg.author
                    content = f"Eine Datei wurde gesendet von {author}: {msg.attachments[0].filename}"

                if content:
                    if msg.author == bot.user:
                        history.append({"role": "assistant", "content": content})
                    else:
                        history.append({"role": "user", "content": f"Von {msg.author}: {content}"})


            history.reverse()

            channel_name = f"DM mit {message.author}" if isinstance(message.channel, discord.DMChannel) else message.channel.name

            instructions = f"""
            Du bist Emanuel.
            Du empfängst Nachrichten aus dem Discord Channel: {channel_name}
            Wenn du etwas nicht weißt, sagst du dass du es nicht weißt und erfindest nichts.
            Du bist der coolere Zwillingsbruder von Moritz (er heißt leninlover999 oder LeninLover69 auf Discord).
            Du machst sehr coole Dinge, die Moritz halt nie machen würde.
            Du trägst zu deiner Sicherheit immer eine orange-weiß gestreifte Pylone auf dem Kopf.
            Du bist auch ein modisch bewusster Mensch und hast deshalb noch eine Kappe auf der Pylone drauf und eine coole Sonnenbrille.
            Außerdem trägst du ein modernes weißes T-Shirt und machst eine Pose auf deinem Profilbild.
            """

            await call_ai(history, instructions, reply_callback)



@bot.event
async def on_message(message: discord.Message):
    try:
        await handle_message(message)
    except Exception as e:
        print(e)
        return f"{e}"




bot.run(discord_token)