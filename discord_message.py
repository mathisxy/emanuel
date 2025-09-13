import asyncio
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, runtime_checkable, Protocol

import discord
from discord import Message, TextChannel


@dataclass
class DiscordMessage:
    value: any

@dataclass
class DiscordMessageReply(DiscordMessage):
    value: str

@dataclass
class DiscordMessageFile(DiscordMessage):
    value: bytes
    filename: str

@dataclass
class DiscordMessageTmpMixin:
    key: str

@runtime_checkable
class DiscordMessageTmpProtocol(Protocol):
    key: str
    value: any

@dataclass
class DiscordMessageReplyTmp(DiscordMessageReply, DiscordMessageTmpMixin):
    pass

@dataclass
class DiscordMessageFileTmp(DiscordMessageFile, DiscordMessageTmpMixin):
    pass

@dataclass
class DiscordMessageProgressTmp(DiscordMessage, DiscordMessageTmpMixin):
    progress: float
    total: float
    length: int = 20
    filled_char: str = '█'
    empty_char: str = '░'
    value: str = field(init=False)

    def __post_init__(self):
        percent = self.progress / self.total if self.total else 0
        filled_length = int(self.length * percent)
        bar = self.filled_char * filled_length + self.empty_char * (self.length - filled_length)
        self.value = f"[{bar}] {int(percent * 100)}% ({int(self.progress)}/{int(self.total)})"

@dataclass
class DiscordMessageRemoveTmp(DiscordMessage, DiscordMessageTmpMixin):
    value: None = field(init=False)
    pass



class DiscordTemporaryMessagesController:

    def __init__(self, channel: TextChannel, error_deletion_delay:float=10, min_update_interval:float=1):
        self.channel = channel
        self._lock = asyncio.Lock()
        self.messages: Dict[str, Message] = {}
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
                if message.key in self.messages.keys():
                    embeds = self.messages[message.key].embeds
                    if embeds:
                        embed = embeds[0]
                        embed.set_image(url=f"attachment://{message.filename}")
                        await self.messages[message.key].edit(embed=embed, view=view, attachments=[file])
                    else:
                        await self.messages[message.key].edit(view=view, attachments=[file])
                    print("EDITED TEMP FILE")
                    print(self.messages)
                else:
                    self.messages[message.key] = await self.channel.send(view=view, file=file)
                    print("ADDED TEMP FILE")
                    print(self.messages)
            elif isinstance(message, DiscordMessageReplyTmp) or isinstance(message, DiscordMessageProgressTmp):
                embed = discord.Embed(
                    description=message.value,
                    color=discord.Color.dark_gray()
                )
                if message.key in self.messages.keys():
                    embeds = self.messages[message.key].embeds
                    if embeds:
                        embed = embeds[0]
                        embed.description = message.value
                    await self.messages[message.key].edit(view=view, embed=embed)
                    print("EDITED TEMP MESSAGE")
                    print(self.messages)
                else:
                    self.messages[message.key] = await self.channel.send(view=view, embed=embed)
                    print("ADDED TEMP MESSAGE")
                    print(self.messages)
            elif isinstance(message, DiscordMessageRemoveTmp):
                msg = self.messages.pop(message.key, None)
                if msg:
                    await msg.delete()

            else:
                logging.error(f"Ungültiger Temp Message Typ: {message}")

    async def __aenter__(self):
        # Init-Logik hier, wenn nötig
        print("Controller gestartet")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            print("DELETING TEMP MESSAGES")
            print(self.messages)
            for key, message in self.messages.items():
                if key == "error":
                    await asyncio.sleep(self.error_deletion_delay)

                await message.delete()

        self.messages = {}
