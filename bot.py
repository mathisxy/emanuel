import asyncio
import io
import logging
from typing import List, Dict

import discord
import pytz
from discord.ext import commands
from dotenv import load_dotenv
import os

from core.config import Config
from core.message_handling import clean_reply, get_member_list
from core.logging_config import setup_logging
from core.discord_buttons import ProgressButton
from core.discord_messages import DiscordMessage, DiscordMessageFile, DiscordMessageReply, \
    DiscordMessageTmpMixin, DiscordTemporaryMessagesController, DiscordMessageReplyTmp, DiscordMessageProgressTmp
from providers.mistral import MistralLLM
from providers.ollama import OllamaLLM

load_dotenv()

setup_logging()


# Discord Intents
intents = discord.Intents.default()
intents.message_content = True  # Für Textnachrichten lesen
intents.messages = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)


match Config.AI:
    case "ollama":
        pass
        llm = OllamaLLM()
    case "mistral":
        pass
        llm = MistralLLM()


async def call_ai(history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage|None], channel: str, use_help_bot: bool = True):
    try:
        await llm.call(history, instructions, queue, channel, use_help_bot)
    except Exception as e:
        logging.exception(e, exc_info=True)
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
                                if event.cancelable:
                                    view = ProgressButton()

                                await tmp_controller.set_message(event, view)

                            elif isinstance(event, DiscordMessageFile):

                                file = discord.File(io.BytesIO(event.value), filename=event.filename)
                                await message.channel.send(file=file)

                            elif isinstance(event, DiscordMessageReply):
                                reply = clean_reply(event.value)
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
                            logging.exception(e, exc_info=True)


                history = []
                async for msg in message.channel.history(limit=Config.TOTAL_MESSAGE_SEARCH_COUNT, oldest_first=False):

                    if msg.content == Config.HISTORY_RESET_TEXT:
                        break

                    if len(history) >= Config.MAX_MESSAGE_COUNT:
                        break

                    role = "assistant" if msg.author == bot.user else "user"
                    timestamp = msg.created_at.astimezone(pytz.timezone("Europe/Berlin")).strftime("%H:%M:%S")
                    content = msg.content if msg.author == bot.user else f"<#Nachricht von <@{msg.author.id}> um {timestamp}> {msg.content}"
                    images = []

                    if msg.attachments:
                        for attachment in msg.attachments:

                            if attachment.content_type and Config.IMAGE_MODEL and attachment.content_type in Config.IMAGE_MODEL_TYPES:
                                image_bytes = await attachment.read()
                                image_filename = attachment.filename

                                save_path = os.path.join("downloads", image_filename)
                                os.makedirs("downloads", exist_ok=True)

                                with open(save_path, "wb") as f:
                                    f.write(image_bytes)

                                images.append(save_path)

                                content += f"\n<#Bildname: {attachment.filename}>"
                            elif attachment.content_type and "text" in attachment.content_type:
                                text_bytes = await attachment.read()
                                text_content = text_bytes.decode("utf-8")

                                content += f"\n<#Dateiname: {attachment.filename}, ausgelesener Inhalt folgt:>\n{text_content}"
                            else:
                                content += f"\n<#Dateiname: {attachment.filename}>"

                    if not content and not images:
                        continue

                    history.append({"role": role, "content": content, **({"images": images} if images else {})})

                history.reverse() # Hoffentlich nicht

                logging.info(history)


                channel_name = message.author.display_name if isinstance(message.channel, discord.DMChannel) else message.channel.name
                use_help_bot = isinstance(message.channel, discord.TextChannel)

                if not isinstance(message.channel, discord.DMChannel):

                    member_list = get_member_list(message.channel.members)
                    member_list = "\n".join([f" - {m}" for m in member_list])

                    logging.info(member_list)

                    instructions = f"""Du bist im Discord Channel: {message.channel.name}
                    
Hier ist eine Liste aller Mitglieder die du gerne taggen kannst:
{member_list}
                    
Wenn du jemanden erwähnen willst, benutze immer exakt die Form <@Discord ID> (z.B: <@123456789123456789>).
                    
""" # TODO modularisieren + Sprachauswahl

                else:
                    instructions = f"Du bist im DM Chat mit {message.author.display_name}.\n"

                instructions += Config.INSTRUCTIONS

                instructions = instructions.replace("[#NAME]", Config.NAME)
                instructions = instructions.replace("[#DISCORD_ID]", Config.DISCORD_ID)

                logging.info(instructions)

                task1 = asyncio.create_task(listener(queue))
                task2 = asyncio.create_task(call_ai(history, instructions, queue, channel_name, use_help_bot))

                await asyncio.gather(task1, task2)


            except Exception as e:
                logging.error(e, exc_info=True)
                await message.channel.send(str(e))


@bot.event
async def on_message(message: discord.Message):
    try:
        await handle_message(message)
    except Exception as e:
        logging.exception(e)
        await message.reply(f"Fehler: {e}")


@bot.event
async def on_ready():
    logging.info(f"🤖 Bot online als {bot.user}!")
    # Alle Cogs laden
    await bot.load_extension("cogs.commands")
    await bot.tree.sync()
    logging.info("✅ Slash-Commands synchronisiert")



bot.run(Config.DISCORD_TOKEN)
