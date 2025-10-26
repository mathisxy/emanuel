import asyncio
from typing import List, Dict
from mistralai import Mistral
from mistralai.extra.mcp.sse import MCPClientSSE, SSEServerParams
from mistralai.extra.run.context import RunContext

from core.config import Config
from discord_message import DiscordMessage, DiscordMessageReply
from providers.base import BaseLLM, LLMResponse
from providers.utils.chat import LLMChat
from providers.utils.mcp_client_integration import generate_with_mcp

client = Mistral(api_key=Config.MISTRAL_API_KEY)

class MistralLLM(BaseLLM):

    async def call(self, history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage | None],
                   channel: str, use_help_bot=False):

        await super().call(history, instructions, queue, channel)

        self.chats[channel].update_history(history)

        if Config.MCP_SERVER_URL:
            await generate_with_mcp(self, self.chats[channel], queue)
        else:
            response = await self.generate(self.chats[channel])
            await queue.put(DiscordMessageReply(response.text))


    async def generate(self, chat: LLMChat, model_name: str | None = None, temperature: float | None = None,
                       timeout: float | None = None, tools: List[Dict] | None = None) -> LLMResponse:

        async with RunContext(model=Config.MISTRAL_MODEL) as run_ctx:
            run_results = await client.beta.conversations.run_async(
                run_ctx=run_ctx,
                inputs=chat.history[1:],
                #description="Manuel, ein Discord Bot",
                instructions=chat.system_entry
            )
            return LLMResponse(run_results.output_as_text)


# async def call_ai(history: List[Dict], instructions: str) -> str:
#     mcp_client = MCPClientSSE(sse_params=SSEServerParams(url=mcp_server_url, timeout=100))
#
#     async with RunContext(model=model) as run_ctx:
#         await run_ctx.register_mcp_client(mcp_client=mcp_client)
#         run_results = await client.beta.conversations.run_async(
#             run_ctx=run_ctx,
#             inputs=history,
#             description="Manuel, ein Discord Bot",
#             instructions=instructions
#         )
#         return run_results.output_as_text