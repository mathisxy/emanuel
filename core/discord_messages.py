import asyncio
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, runtime_checkable, Protocol, Tuple

import discord
from discord import Message, TextChannel


@dataclass(kw_only=True)
class DiscordMessage:
    value: any

@dataclass(kw_only=True)
class DiscordMessageReply(DiscordMessage):
    value: str

@dataclass(kw_only=True)
class DiscordMessageFile(DiscordMessage):
    value: bytes
    filename: str

@dataclass(kw_only=True)
class DiscordMessageTmpMixin:
    key: str

@runtime_checkable
class DiscordMessageTmpProtocol(Protocol):
    key: str
    value: any

@dataclass(kw_only=True)
class DiscordMessageReplyTmp(DiscordMessageReply, DiscordMessageTmpMixin):
    embed: bool = True

@dataclass(kw_only=True)
class DiscordMessageFileTmp(DiscordMessageFile, DiscordMessageTmpMixin):
    key: str = "progress"

@dataclass(kw_only=True)
class DiscordMessageProgressTmp(DiscordMessage, DiscordMessageTmpMixin):
    progress: float
    total: float
    length: int = 20
    filled_char: str = '█'
    empty_char: str = '░'
    cancelable: bool = False
    key: str = "progress"
    value: str = field(init=False)

    def __post_init__(self):
        percent = self.progress / self.total if self.total else 0
        filled_length = int(self.length * percent)
        bar = self.filled_char * filled_length + self.empty_char * (self.length - filled_length)
        self.value = f"[{bar}] {int(percent * 100)}% ({int(self.progress)}/{int(self.total)})"

@dataclass(kw_only=True)
class DiscordMessageReplyTmpError(DiscordMessageReplyTmp):
    deletion_delay = None
    key: str = "error"

@dataclass(kw_only=True)
class DiscordMessageRemoveTmp(DiscordMessage, DiscordMessageTmpMixin):
    value: None = field(init=False)
    pass



class DiscordTemporaryMessagesController:

    def __init__(self, channel: TextChannel, error_deletion_delay:float=10, min_update_interval:float=1):
        self.channel = channel
        self._lock = asyncio.Lock()
        self.messages: Dict[str, Tuple[DiscordMessageTmpProtocol, Message]] = {}
        self.error_deletion_delay = error_deletion_delay
        self.min_update_interval = min_update_interval
        self._last_update: Dict[str, float] = {}


    async def set_message(self, message: DiscordMessageTmpProtocol, view: discord.ui.View = None):

        now = time.monotonic()

        # Wenn es sich um Progress handelt → throttlen
        if isinstance(message, DiscordMessageProgressTmp):
            last = self._last_update.get(message.key, 0)
            # Update nur, wenn Intervall überschritten oder 100% erreicht
            if now - last < self.min_update_interval and message.progress < message.total:
                return
            self._last_update[message.key] = now


        async with self._lock:

            if isinstance(message, DiscordMessageFileTmp):
                file = discord.File(io.BytesIO(message.value), filename=message.filename)
                if message.key in self.messages:
                    _, discord_msg = self.messages[message.key]
                    embeds = discord_msg.embeds
                    if embeds:
                        embed = embeds[0]
                        embed.set_image(url=f"attachment://{message.filename}")
                        await discord_msg.edit(embed=embed, view=view, attachments=[file])
                    else:
                        await discord_msg.edit(view=view, attachments=[file])
                    self.messages[message.key] = (message, discord_msg)
                else:
                    self.messages[message.key] = (message, await self.channel.send(view=view, file=file))
            elif isinstance(message, DiscordMessageReplyTmp) or isinstance(message, DiscordMessageProgressTmp):
                with_embed = (not isinstance(message, DiscordMessageReplyTmp)) or message.embed

                embed = discord.Embed(
                    description=message.value,
                    color=discord.Color.dark_gray()
                ) if with_embed else None

                if message.key in self.messages:
                    _, discord_msg = self.messages[message.key]
                    if embed and discord_msg.embeds:
                        embed = discord_msg.embeds[0]
                        embed.description = message.value

                    await discord_msg.edit(view=view, embed=embed, content=None if embed else message.value)
                    self.messages[message.key] = (message, discord_msg)

                else:
                    self.messages[message.key] = (message, await self.channel.send(view=view, embed=embed, content=None if embed else message.value))
            elif isinstance(message, DiscordMessageRemoveTmp):
                msg = self.messages.pop(message.key, None)
                if msg:
                    _, discord_msg = msg
                    await discord_msg.delete()
            else:
                logging.error(f"Ungültiger Temp Message Typ: {message}")


    async def __aenter__(self):
        logging.debug("Discord Controller gestartet")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            logging.debug("Temporäre Discord Nachrichten werden gelöscht")
            logging.debug(self.messages)

            tasks = []

            for key, message in self.messages.items():
                protocol_msg, discord_msg = message
                if isinstance(protocol_msg, DiscordMessageReplyTmpError):
                    async def delete_with_delay(protocol_msg: DiscordMessageReplyTmpError, discord_msg: Message):
                        await asyncio.sleep(protocol_msg.deletion_delay if protocol_msg.deletion_delay else self.error_deletion_delay)
                        await discord_msg.delete()
                    tasks.append(delete_with_delay(protocol_msg, discord_msg))
                else:
                    await discord_msg.delete()

            await asyncio.gather(*tasks)

        self.messages = {}