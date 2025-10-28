import logging
from asyncio import Queue
from typing import List, Tuple

from fastmcp.client.logging import LogMessage
from mcp import Tool
from mcp.types import CallToolResult

from core.discord_messages import DiscordMessage
from providers.utils.chat import LLMChat


class MCPIntegration:

    def __init__(self, queue: Queue[DiscordMessage]):
        self.queue = queue

    # ---------- Logging ----------
    async def log_handler(self, message: LogMessage):
        pass

    # ---------- Progress ----------
    async def progress_handler(self, progress: float, total: float|None, message: str|None):
        pass

    # ---------- Tool Filtering ----------
    def filter_tool_list(self, tools: List[Tool]) -> List[Tool]:
        return tools

    # ---------- Tool Result Processing ----------
    async def process_tool_result(self,
                                  name: str,
                                  result: CallToolResult,
                                  chat: LLMChat,
                                  ) -> bool:

        """Returned boolean indicates whether the LLM should be called again"""

        logging.debug(result)

        result_str = str(result.data) # Nur Text, Multimedia führt zu None im Result

        logging.info(result_str)

        chat.history.append({"role": "system", "content": f"#{{tool_result für {name}: {result_str}}}"})