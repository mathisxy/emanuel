import asyncio
import logging
from typing import List, Dict

import tiktoken
from GPUtil import GPUtil
from ollama import AsyncClient

from core.config import Config


class LLMChat:

    client: AsyncClient
    lock: asyncio.Lock
    history: List[Dict[str, str]]
    tokenizer: tiktoken

    max_tokens = 3700 if len(GPUtil.getGPUs()) == 0 else Config.MAX_TOKENS
    logging.debug(f"MAX TOKENS: {max_tokens}")

    def __init__(self):

        self.client = AsyncClient(host=Config.OLLAMA_URL)
        self.lock = asyncio.Lock()
        self.history = []
        self.tokenizer = tiktoken.get_encoding("cl100k_base")


    @property
    def system_entry(self) -> Dict[str, str] | None:
        if self.history:
            return self.history[0]
        return None

    @system_entry.setter
    def system_entry(self, value: Dict[str, str]):
        if not self.history:
            self.history = [value]
        else:
            self.history[0] = value

    def update_history(self, new_history: List[Dict[str, str]], instructions_entry: Dict[str, str]|None = None, min_overlap=1):

        history_without_tool_results = [x for x in self.history if not (x["role"] == "system" and x["content"].startswith('#'))]

        #print("HISTORY WITHOUT TOOLS")
        #print(history_without_tool_results)
        #print(new_history)

        max_overlap_length = len(history_without_tool_results)
        overlap_length = None

        for length in range(max_overlap_length, min_overlap, -1):
            if history_without_tool_results[-length:] == new_history[:length]:
                overlap_length = length
                logging.info(f"OVERLAP LENGTH: {overlap_length}")
                break

        if not overlap_length:
            logging.info("KEIN OVERLAP")
            logging.info(self.history)
            logging.info(new_history)
            self.history = [instructions_entry] if instructions_entry else []
            self.history.extend(new_history)
        elif instructions_entry:
            if self.history[0] == instructions_entry:
                self.history = self.history + new_history[overlap_length:]
            else:
                logging.info("NEW INSTRUCTIONS")
                logging.info(self.history[0])
                logging.info(instructions_entry)
                self.history = [instructions_entry]
                self.history.extend(new_history)
        else:
            self.history = self.history + new_history[overlap_length:]

        logging.info(self.count_tokens())

        if self.count_tokens() > self.max_tokens:
            logging.info("CUTTING BECAUSE OF EXCEEDING TOKEN COUNT")
            self.history = new_history


    def build_prompt(self, history=None) -> str:
        if history is None:
            history = self.history

        prompt_lines = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_lines.append(f"{role}: {content}")
        return "\n".join(prompt_lines)

    def count_tokens(self, history=None) -> int:
        prompt = self.build_prompt(history)
        return len(self.tokenizer.encode(prompt))