import asyncio
import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Type

from core.config import Config
from core.discord_messages import DiscordMessage
from providers.utils import mcp_client_integrations
from providers.utils.chat import LLMChat
from providers.utils.mcp_client_integrations.base import MCPIntegration


@dataclass
class LLMToolCall:
    name: str
    arguments: Dict

@dataclass
class LLMResponse:
    text: str
    tool_calls: List[LLMToolCall] = field(default_factory=list)


class BaseLLM(ABC):

    def __init__(self):
        self.chats: Dict[str, LLMChat] = {}
        self.mcp_client_integration_module: Type[MCPIntegration] = self.load_mcp_integration_class()

    @abstractmethod
    async def call(self, history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage | None], channel: str):

        self.chats.setdefault(channel, LLMChat())


    @abstractmethod
    async def generate(self, chat: LLMChat, model_name: str | None = None, temperature: float | None = None, timeout: float | None = None, tools: List[Dict] | None = None) -> LLMResponse:
        pass


    @staticmethod
    def load_mcp_integration_class():

        class_name = Config.MCP_INTEGRATION_CLASS

        for _, module_name, _ in pkgutil.iter_modules(mcp_client_integrations.__path__):
            logging.debug(module_name)
            module = importlib.import_module(f"providers.utils.mcp_client_integrations.{module_name}")
            logging.debug(module)
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                return cls

        from providers.utils.mcp_client_integrations.base import MCPIntegration
        return MCPIntegration