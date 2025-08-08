import os
import subprocess
from enum import Enum

import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.exceptions import ToolError

from actions import EmanuelActions

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
WORKER_SERVICE = os.getenv("WORKER_SERVICE", "emanuel")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

class EmanuelAction(str, Enum):
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    INTERRUPT = "interrupt_image_generation"
    UNLOAD_COMFY = "unload_comfy_models"


@bot.event
async def on_ready():
    print(f"Controller online als {bot.user}!")
    await bot.tree.sync()

@app_commands.choices(action=[
    app_commands.Choice(name="Stoppen", value=EmanuelAction.STOP),
    app_commands.Choice(name="Starten", value=EmanuelAction.START),
    app_commands.Choice(name="Neustarten", value=EmanuelAction.RESTART),
    app_commands.Choice(name="Bildgenerierung abbrechen", value=EmanuelAction.INTERRUPT),
    app_commands.Choice(name="Bildgenerierungsmodelle aus VRAM entfernen", value=EmanuelAction.UNLOAD_COMFY)
])
@bot.tree.command(name="emanuel", description="Steuere Emanuel")
async def emanuel(interaction: discord.Interaction, action: app_commands.Choice[str]):

    try:
        emanuel_action = EmanuelAction(action.value)
        await interaction.response.send_message(await EmanuelActions.execute(emanuel_action), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Ausnahmefehler: {str(e)}", ephemeral=True)


bot.run(discord_token)
