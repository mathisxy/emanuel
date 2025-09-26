import asyncio
import importlib
import io
import logging
import re
from typing import List, Dict

import discord
import pytz
from discord import Status
from discord.ext import commands
from dotenv import load_dotenv
import os

from discord_buttons import ProgressButton
from discord_message import DiscordMessage, DiscordMessageFile, DiscordMessageReply, \
    DiscordMessageTmpMixin, DiscordTemporaryMessagesController, DiscordMessageReplyTmp

logging.basicConfig(filename="bot.log", level=logging.INFO)
load_dotenv()

api_key = os.getenv("API_KEY")
model = os.getenv("MODEL")
discord_token = os.getenv("DISCORD_TOKEN")
mcp_server_url = os.getenv("MCP_SERVER_URL")
ai=os.getenv("AI", "mistral")

intents = discord.Intents.default()
intents.message_content = True  # Für Textnachrichten lesen
intents.messages = True
intents.members = True
intents.presences = True

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

                    if msg.content == os.getenv("HISTORY_RESET_TEXT"):
                        break

                    if len(history) >= max_count:
                        break

                    #if msg.author != bot.user: #and not is_relevant_message(msg):
                        #continue

                    role = "assistant" if msg.author == bot.user else "user"
                    content = msg.content if role != "user" else f"[#{msg.created_at.astimezone(pytz.timezone('Europe/Berlin')).strftime("%H:%M:%S")} von {msg.author.display_name}] {msg.content}"
                    images = []

                    if msg.attachments:
                        for attachment in msg.attachments:

                            if attachment.content_type and attachment.content_type in ["image/png", "image/jpeg"]:
                                image_bytes = await attachment.read()
                                image_filename = attachment.filename

                                save_path = os.path.join("downloads", image_filename)
                                os.makedirs("downloads", exist_ok=True)

                                with open(save_path, "wb") as f:
                                    f.write(image_bytes)

                                images.append(save_path)

                                content += f"\n[#Bildname: {attachment.filename}]"
                            elif attachment.content_type and "text" in attachment.content_type:
                                text_bytes = await attachment.read()
                                text_content = text_bytes.decode("utf-8")

                                content += f"\n[#Dateiname: {attachment.filename}, ausgelesener Inhalt folgt:]\n{text_content}"
                            else:
                                content += f"\n[#Dateiname: {attachment.filename}]"

                    if not content and not images:
                        continue

                    history.append({"role": role, "content": content, **({"images": images} if images else {})})

                history.reverse()

                instructions = f"Du bist {os.getenv("NAME")}. "

                channel_name = message.author.display_name if isinstance(message.channel, discord.DMChannel) else message.channel.name

                if not isinstance(message.channel, discord.DMChannel):

                    member_list = "\n".join([f"- {m.display_name}: <@{m.id}>" for m in message.channel.members if m.status in [Status.online, Status.idle] ])

                    logging.info(member_list)

                    instructions += f"""Du bist im Discord Channel: {message.channel.name}
                    
                    Hier ist eine Liste aller Mitglieder die du gerne taggen kannst:
                    {member_list}
                    
                    Wenn du jemanden erwähnen willst, benutze immer exakt die Form <@ID> (z.B: <@123456789>).
                    
                    """

                else:
                    instructions += f"Du bist im DM Chat mit {message.author.display_name}.\n"

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


@bot.event
async def on_ready():
    print(f"🤖 Bot online als {bot.user}!")
    # Alle Cogs laden
    await bot.load_extension("cogs.commands")
    await bot.tree.sync()
    print("✅ Slash-Commands synchronisiert")


bot.run(discord_token)
