import csv
import logging
import os
from typing import List, Dict

import discord
from discord import Status

from core.config import Config


def get_instructions_from_discord_info(message: discord.Message) -> str:

    if not isinstance(message.channel, discord.DMChannel):

        member_list = get_member_list(message.channel.members)
        member_list = "\n".join([f" - {m}" for m in member_list])

        logging.info(member_list)

        match Config.LANGUAGE:
            case "de":
                instructions = f"""Du befindest dich im Discord-Channel: {message.channel.name}.

Untenstehend findest du eine Liste aller Mitglieder, die du erwähnen kannst:
{member_list}

Wenn du ein Mitglied erwähnen möchtest, benutze immer exakt folgendes Format: <@Discord ID> 
(z.B.: <@123456789123456789>). Ändere das Format nicht und achte darauf, dass die spitzen Klammern sowie die numerische ID enthalten sind.

"""

            case "en":
                instructions = f"""You are currently in the Discord channel: {message.channel.name}.

Here is a list of all members that you can mention:
{member_list}

When mentioning a user, always use the exact format <@Discord ID> (for example: <@123456789123456789>).
Do not modify the format, and make sure to include the angle brackets and the numeric ID.

"""

            case _:
                raise TypeError(f"Invalid Language: {Config.LANGUAGE}")


    else:
        match Config.LANGUAGE:
            case "de":
                instructions = f"Du bist im direct message (DM) Chat mit {message.author.display_name}.\n"
            case "en":
                instructions = f"You are in a direct message (DM) chat with {message.author.display_name}.\n"
            case _:
                raise TypeError(f"Invalid Language: {Config.LANGUAGE}")

    return instructions


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