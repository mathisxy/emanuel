import base64
import logging
import mimetypes
import os
import secrets
from typing import List

from fastmcp.client.logging import LogMessage
from mcp import Tool
from mcp.types import CallToolResult

from core.config import Config
from core.discord_messages import DiscordMessageFileTmp, DiscordMessageReplyTmp, \
    DiscordMessageProgressTmp, DiscordMessageFile
from providers.utils.chat import LLMChat
from providers.utils.mcp_client import construct_tool_call_results
from providers.utils.mcp_client_integrations.base import MCPIntegration


class MultimediaMCPIntegration(MCPIntegration):

    # ---------- Logging ----------
    async def log_handler(self, message: LogMessage):
        if message.data.get("msg") == "preview_image":
            image_base64 = message.data.get("extra").get("base64")
            image_type = message.data.get("extra").get("type")
            image_bytes = base64.b64decode(image_base64)
            await self.queue.put(DiscordMessageFileTmp(value=image_bytes, filename=f"preview.{image_type}", cancelable=True))
        else:
            await self.queue.put(DiscordMessageReplyTmp(value=str(message.data.get("msg")), key=message.level.lower()))

    # ---------- Progress ----------
    async def progress_handler(self, progress: float, total: float|None, message: str|None):
        logging.debug(f"Progress: {progress}/{total}:{message}")
        await self.queue.put(DiscordMessageProgressTmp(progress=progress, total=total, cancelable=True))

    def filter_tool_list(self, tools: List[Tool]) -> List[Tool]:

        tags = Config.MCP_TOOL_TAGS
        logging.info(tags)

        return [
            tool for tool in tools
            if hasattr(tool, 'meta') and tool.meta and
               tool.meta.get('_fastmcp', {}) and
               any(tag in tool.meta['_fastmcp'].get('tags', []) for tag in tags)
        ]


    # ---------- Tool Result Processing ----------
    async def process_tool_result(self,
                                  name: str,
                                  result: CallToolResult,
                                  chat: LLMChat,
                                  ) -> bool:

        """Returned boolean indicates whether the LLM should be called again"""

        if not result.content:
            raise Exception(f"Das Tool Result hat keinen Inhalt.")
        logging.info(result.content[0].type)

        if result.content[0].type == "text":
            logging.info(result.content[0].text)

        if result.content[0].type == "image" or result.content[0].type == "audio":

            file_content = base64.b64decode(result.content[0].data)
            media_type = result.content[0].mimeType
            logging.debug(media_type)
            ext = mimetypes.guess_extension(media_type)
            logging.debug(ext)

            filename = f"{secrets.token_urlsafe(8)}{ext}"

            if result.content[0].type == "image":

                await self.queue.put(DiscordMessageFile(value=file_content, filename=filename))
                chat.history.append({"role": "assistant", "content": "", "images": [os.path.join("downloads", filename)]})

            else:
                await self.queue.put(DiscordMessageFile(value=file_content, filename=filename))
                chat.history.append({"role": "assistant", "content": f"Du hast eine Datei gesendet: {filename}"})

            # Damit die Datei schonmal gespeichert ist
            with open(os.path.join("downloads", filename), "wb") as f:
                f.write(file_content)

            return False

        else:

            result_str = str(result.data)

            logging.info(result_str)

            chat.history.append(construct_tool_call_results(name, result_str))

            return True

