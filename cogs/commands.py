import discord

from discord import app_commands
from discord.ext import commands

from core.config import Config
from core.discord_actions import BotActions, BotAction


class CommandsCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ CommandsCog geladen")

    @app_commands.choices(action=[
        app_commands.Choice(name="Bildgenerierung abbrechen", value=BotActions.INTERRUPT),
        app_commands.Choice(name="Bildgenerierungsmodelle aus VRAM entfernen", value=BotActions.UNLOAD_COMFY),
        app_commands.Choice(name="Nachrichtenverlauf zurücksetzen", value=BotActions.RESET)
    ])

    @app_commands.command(name=Config.COMMAND_NAME, description="Steuere den Bot")
    async def emanuel(self, interaction: discord.Interaction, action: app_commands.Choice[str]):

        try:
            emanuel_action = BotActions(action.value)
            await interaction.response.send_message(await BotAction.execute(emanuel_action, interaction), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Fehler: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsCog(bot))
