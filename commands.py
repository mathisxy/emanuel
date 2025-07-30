import os
import subprocess
from enum import Enum

import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sympy.logic.boolalg import Exclusive

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

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


@bot.event
async def on_ready():
    print(f"Controller online als {bot.user}!")
    await bot.tree.sync()

@app_commands.choices(action=[
    app_commands.Choice(name="Stoppen", value=EmanuelAction.STOP),
    app_commands.Choice(name="Starten", value=EmanuelAction.START),
    app_commands.Choice(name="Neustarten", value=EmanuelAction.RESTART),
    app_commands.Choice(name="Bildgenerierung abbrechen", value=EmanuelAction.INTERRUPT)
])
@bot.tree.command(name="emanuel", description="Steuere Emanuel")
async def emanuel(interaction: discord.Interaction, action: app_commands.Choice[str]):

    try:

        if action.value == EmanuelAction.INTERRUPT:

            client = Client(os.getenv("MCP_SERVER_URL"))

            async with client:
                try:
                    await client.call_tool("interrupt_image_generation", {})
                    await interaction.response.send_message(f"🛑 Bildgenerierung abgebrochen")
                except ToolError as e:
                    await interaction.response.send_message(f"❌ Ausnahmefehler: {str(e)}")



            # async with streamablehttp_client(os.getenv("MCP_SERVER_URL")) as (
            #         read_stream,
            #         write_stream,
            #         _,
            # ):
            #     # Create a session using the client streams
            #     async with ClientSession(read_stream, write_stream) as session:
            #
            #         try:
            #             # Initialize the connection
            #             await session.initialize()
            #             result = await session.call_tool("interrupt_image_generation", {})
            #             if result.isError:
            #                 raise Exception(result.content[0].text)
            #             else:
            #                 await interaction.response.send_message(f"🛑 Bildgenerierung abgebrochen")
            #         except Exception as e:
            #             await interaction.response.send_message(f"❌ Ausnahmefehler: {str(e)}")


        else:

            result = subprocess.run(
                ["sudo", "service", WORKER_SERVICE, action.value],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                await interaction.response.send_message(f"✅ {action.name} erfolgreich ausgeführt.")
            else:
                await interaction.response.send_message(f"❌ Fehler:\n```\n{result.stderr.strip()}\n```")
    except Exception as e:
        await interaction.response.send_message(f"❌ Abrakadabra-Ausnahmefehler: {str(e)}")


bot.run(discord_token)
