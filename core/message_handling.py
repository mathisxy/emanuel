import logging
import re


def clean_reply(reply: str) -> str:

    pattern = r'(<#.*?>)' # If the LLM replicates the used information tags
    reply = re.sub(pattern, '', reply)
    logging.info(f"REPLY: {reply}")
    return reply.strip()