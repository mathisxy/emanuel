import csv
import logging
import os
import re
from typing import List, Dict

import discord
from discord import Status

from core.config import Config


def get_member_list(members: List[discord.Member]) -> List[Dict[str, str | int]]:

    member_dict = {m.id: {"Discord": m.display_name, "Discord ID": m.id} for m in members if m.status in [Status.online, Status.idle]}
    extra_dict = {}
    if Config.USERNAMES_CSV_FILE_PATH and os.path.exists(Config.USERNAMES_CSV_FILE_PATH):
        with open(Config.USERNAMES_CSV_FILE_PATH, 'r', encoding='utf-8') as datei:
            csv_reader = csv.DictReader(datei)
            extra_dict = {int(row["Discord ID"]): {**row, "Discord ID": int(row["Discord ID"])} for row in csv_reader}

    return [
        { **extra_dict.get(key, {}), **member_dict.get(key, {}) }
        for key in (member_dict.keys() | extra_dict.keys())
    ]

def clean_reply(reply: str) -> str:

    pattern = r'(<start_of_image>|\<#.*?>)' # TODO Gemma spezifisches pattern zu ollama schieben
    reply = re.sub(pattern, '', reply)
    logging.info(f"REPLY: {reply}")
    return reply.strip()