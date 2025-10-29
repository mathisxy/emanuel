import asyncio
import json
from typing import List, Dict
from mistralai import Mistral

from core.config import Config
from core.discord_messages import DiscordMessage, DiscordMessageReply
from providers.base import BaseLLM, LLMResponse, LLMToolCall
from providers.utils.chat import LLMChat
from providers.utils.mcp_client import generate_with_mcp

client = Mistral(api_key=Config.MISTRAL_API_KEY)

class MistralLLM(BaseLLM):

    async def call(self, history: List[Dict], instructions: str, queue: asyncio.Queue[DiscordMessage | None],
                   channel: str, use_help_bot=False):

        await super().call(history, instructions, queue, channel)

        instructions_entry = {"role": "system", "content": instructions}
        self.chats[channel].update_history(history, instructions_entry)

        if Config.MCP_INTEGRATION_CLASS:
            await generate_with_mcp(self, self.chats[channel], queue, self.mcp_client_integration_module(queue))
        else:
            response = await self.generate(self.chats[channel])
            await queue.put(DiscordMessageReply(value=response.text))


    async def generate(self, chat: LLMChat, model_name: str | None = None, temperature: float | None = None,
                       timeout: float | None = None, tools: List[Dict] | None = None) -> LLMResponse:

        model_name = model_name if model_name else Config.MISTRAL_MODEL

        # async with RunContext(model=Config.MISTRAL_MODEL) as run_ctx:
        #     run_results = await client.beta.conversations.run_async(
        #         run_ctx=run_ctx,
        #         inputs=chat.history[1:],
        #         #description="Manuel, ein Discord Bot",
        #         instructions=chat.system_entry
        #     )

        response = await client.chat.complete_async(
            model=model_name,
            messages=chat.history,
            temperature=temperature,
            tools=tools,
        )

        message = response.choices[0].message

        tool_calls = []
        if message.tool_calls:
            tool_calls = [LLMToolCall(name=t.function.name, arguments=json.loads(t.function.arguments)) for t in message.tool_calls] if message.tool_calls else []

        return LLMResponse(message.content, tool_calls)


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