import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict

from core.discord_message import DiscordMessage
from providers.utils.chat import LLMChat


@dataclass
class LLMToolCall:
    name: str
    arguments: Dict

@dataclass
class LLMResponse:
    text: str
    tool_calls: List[LLMToolCall] = field(default_factory=list)


class BaseLLM(ABC):

    chats: Dict[str, LLMChat] = {}

    @abstractmethod
    async def call(self, history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage | None], channel: str):

        self.chats.setdefault(channel, LLMChat())


    @abstractmethod
    async def generate(self, chat: LLMChat, model_name: str | None = None, temperature: float | None = None, timeout: float | None = None, tools: List[Dict] | None = None) -> LLMResponse:
        pass