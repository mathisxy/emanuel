import os

import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from actions import EmanuelAction, EmanuelActions

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
WORKER_SERVICE = os.getenv("WORKER_SERVICE", "emanuel")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Controller online als {bot.user}!")
    await bot.tree.sync()

@app_commands.choices(action=[
    app_commands.Choice(name="Stoppen", value=EmanuelActions.STOP),
    app_commands.Choice(name="Starten", value=EmanuelActions.START),
    app_commands.Choice(name="Neustarten", value=EmanuelActions.RESTART),
    app_commands.Choice(name="Bildgenerierung abbrechen", value=EmanuelActions.INTERRUPT),
    app_commands.Choice(name="Bildgenerierungsmodelle aus VRAM entfernen", value=EmanuelActions.UNLOAD_COMFY),
    app_commands.Choice(name="Nachrichtenverlauf zurücksetzen", value=EmanuelActions.RESET)
])
@bot.tree.command(name=os.getenv("COMMAND_NAME"), description="Steuere den Bot")
async def emanuel(interaction: discord.Interaction, action: app_commands.Choice[str]):

    try:
        emanuel_action = EmanuelActions(action.value)
        await interaction.response.send_message(await EmanuelAction.execute(emanuel_action, interaction), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Ausnahmefehler: {str(e)}", ephemeral=True)


bot.run(discord_token)
