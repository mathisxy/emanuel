import discord
from discord.ui import View, Button

from actions import EmanuelActions, EmanuelAction


class ProgressButton(View):

    @discord.ui.button(label="Abbrechen", style=discord.ButtonStyle.primary, custom_id="progress")
    async def regenerate_button(self, interaction: discord.Interaction, button: Button):

        try:
            await interaction.response.send_message(await EmanuelActions.execute(EmanuelAction.INTERRUPT), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ausnahmefehler: {str(e)}", ephemeral=True)
