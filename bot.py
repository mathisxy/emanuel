import asyncio
import importlib
import io
import re
from typing import List, Dict, Literal

import discord
import pytz
from discord.ext import commands
from dotenv import load_dotenv
import os

from discord_buttons import ProgressButton
from discord_message import DiscordMessage, DiscordMessageFile, DiscordMessageReply, \
    DiscordMessageTmpMixin, DiscordTemporaryMessagesController, DiscordMessageReplyTmp

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



async def call_ai(history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage|None], channel: str):
    try:
        await module.call_ai(history, instructions, queue, channel)
    except Exception as e:
        print(f"FEHLER BEI CALL AI: {e}")
        await queue.put(DiscordMessageReplyTmp(value=f"Ein Fehler ist aufgetreten: {str(e)}", key="error"))
    finally:
        await queue.put(None)



def is_relevant_message(message: discord.Message) -> bool:
    return bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)


async def handle_message(message):
    if message.author == bot.user:
        return

    if is_relevant_message(message):

        async with message.channel.typing(), DiscordTemporaryMessagesController(channel=message.channel) as tmp_controller:

            try:

                queue = asyncio.Queue[DiscordMessage]()

                async def listener(queue: asyncio.Queue[DiscordMessage|None]):

                    while True:
                        try:
                            event = await queue.get()
                            if event is None:
                                break
                            if isinstance(event, DiscordMessageTmpMixin):

                                view = None
                                if event.key == "progress":
                                    view = ProgressButton()

                                await tmp_controller.set_message(event, view)

                            elif isinstance(event, DiscordMessageFile):

                                file = discord.File(io.BytesIO(event.value), filename=event.filename)
                                await message.channel.send(file=file)

                            elif isinstance(event, DiscordMessageReply):
                                reply = event.value.strip()
                                pattern = r'(<start_of_image>|\[#.*?\])'
                                reply = re.sub(pattern, '', reply)
                                print(f"REPLY: {reply}")
                                if not reply:
                                    return
                                if len(reply) > 2000:
                                    file = discord.File(io.BytesIO(reply.encode('utf-8')), filename=f"{bot.user.name}s Antwort.txt")
                                    await message.channel.send(file=file)
                                else:
                                    await message.channel.send(reply)

                            else:
                                raise Exception("Ungültiger DiscordMessage Typ")

                        except Exception as e:
                            print(e)


                history = []
                max_count = int(os.getenv("MAX_MESSAGE_COUNT", 3))
                async for msg in message.channel.history(limit=20, oldest_first=False):

                    if msg.content == "Manuel Schmanuel":
                        break

                    if len(history) >= max_count:
                        break

                    #if msg.author != bot.user: #and not is_relevant_message(msg):
                        #continue

                    role = "assistant" if msg.author == bot.user else "user"
                    content = msg.clean_content if role != "user" else f"Um {msg.created_at.astimezone(pytz.timezone('Europe/Berlin')).strftime("%H:%M:%S")} schrieb {msg.author.display_name}: {msg.clean_content}"
                    images = []

                    if msg.attachments:
                        for attachment in msg.attachments:

                            if attachment.content_type and "image" in attachment.content_type:
                                image_bytes = await attachment.read()
                                image_filename = attachment.filename

                                save_path = os.path.join("downloads", image_filename)
                                os.makedirs("downloads", exist_ok=True)

                                with open(save_path, "wb") as f:
                                    f.write(image_bytes)

                                images.append(save_path)

                                content += f"\n[#Bildname: {attachment.filename}]"
                            else:
                                content += f"\n[#Dateiname: {attachment.filename}]"

                    if not content and not images:
                        continue

                    history.append({"role": role, "content": content, "images": images})

                history.reverse()

                channel_name = f"DM mit {message.author.display_name}" if isinstance(message.channel, discord.DMChannel) else message.channel.name

                instructions = f"Du bist {os.getenv("NAME")}. Du bist im Discord Channel: {channel_name}"
                instructions += os.getenv("INSTRUCTIONS")

                task1 = asyncio.create_task(listener(queue))
                task2 = asyncio.create_task(call_ai(history, instructions, queue, channel_name))

                await asyncio.gather(task1, task2)


            except Exception as e:
                await message.channel.send(str(e))


@bot.event
async def on_message(message: discord.Message):
    try:
        await handle_message(message)
    except Exception as e:
        print(e)
        await message.reply(f"Fehler: {e}")



bot.run(discord_token)
