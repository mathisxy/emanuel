import logging

import discord

from core.config import Config


def use_help_bot(message: discord.Message):

    if isinstance(message.channel, discord.TextChannel):

        logging.debug("DISCORD HELP BOT: Discord Text Channel - check if the Help Bot should be used")

        logging.debug("DISCORD HELP BOT: %s", [member.id for member in message.channel.members])
        is_member = Config.MCP_ERROR_HELP_DISCORD_ID in [member.id for member in message.channel.members]

        logging.debug(f"DISCORD HELP BOT: Is {Config.MCP_ERROR_HELP_DISCORD_ID} member: {is_member}")

        return is_member

    return False


