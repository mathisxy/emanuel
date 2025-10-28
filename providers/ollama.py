import asyncio
import logging
from typing import List, Dict, Literal

import tiktoken

from core.config import Config
from core.discord_messages import DiscordMessage, DiscordMessageReply, DiscordMessageReplyTmpError
from providers.base import BaseLLM, LLMResponse, LLMToolCall
from providers.utils.chat import LLMChat
from providers.utils.mcp_client import generate_with_mcp
from providers.utils.vram import wait_for_vram


class OllamaLLM(BaseLLM):

    async def call(self, history: List[Dict[str, str]], instructions: str, queue: asyncio.Queue[DiscordMessage | None],
                   channel: str, use_help_bot=False):

        try:
            await super().call(history, instructions, queue, channel)

            instructions_entry = {"role": "system", "content": instructions}
            self.chats[channel].update_history(history, instructions_entry)

            logging.debug(self.chats[channel].history)

            enc = tiktoken.get_encoding("cl100k_base")  # GPT-ähnlicher Tokenizer
            logging.info(f"System Message Tokens: {len(enc.encode(self.chats[channel].system_entry["content"]))}")

            if Config.MCP_SERVER_URL:
                await generate_with_mcp(self, self.chats[channel], queue, self.mcp_client_integration_module(queue), use_help_bot)
            else:
                response = await self.generate(self.chats[channel])
                await queue.put(DiscordMessageReply(value=response.text))

        except Exception as e:
            logging.error(e, exc_info=True)
            await queue.put(DiscordMessageReplyTmpError(value=str(e)))


    @staticmethod
    async def generate(chat: LLMChat, model_name: str | None = None, temperature: str | None = None, think: bool | Literal["low", "medium", "high"] | None = None, keep_alive: str | float | None = None, timeout: float | None = None, tools: List[Dict] | None = None) -> LLMResponse:

        await wait_for_vram(required_gb=11)

        model_name = model_name if model_name else Config.OLLAMA_MODEL
        temperature = temperature if temperature else Config.OLLAMA_MODEL_TEMPERATURE
        think = think if think else Config.OLLAMA_THINK
        keep_alive = keep_alive if keep_alive else Config.OLLAMA_KEEP_ALIVE
        timeout = timeout if timeout else Config.OLLAMA_TIMEOUT

        async with (chat.lock):

            try:

                response = await asyncio.wait_for(
                    chat.client.chat(
                        model=model_name,
                        messages=chat.history,
                        stream=False,
                        keep_alive=keep_alive,
                        options={
                            **({"temperature": temperature} if temperature is not None else {})
                        },
                        **({"think": think} if think is not None else {}),
                        **({"tools": tools} if tools is not None else {}),
                    ),
                    timeout=timeout,
                )

                logging.info(response)

                tool_calls = [LLMToolCall(name=t.function.name, arguments=dict(t.function.arguments)) for t in response.message.tool_calls] if response.message.tool_calls else []

                return LLMResponse(text=response.message.content, tool_calls=tool_calls)


            except Exception as e:
                logging.error(e, exc_info=True)
                raise Exception(f"Ollama Fehler: {e}")




