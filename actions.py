import os
import subprocess
import traceback
from enum import Enum

import discord
from fastmcp import Client

class EmanuelActions(str, Enum):
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    INTERRUPT = "interrupt_image_generation"
    UNLOAD_COMFY = "unload_comfy_models"
    RESET = "reset"


WORKER_SERVICE = os.getenv("WORKER_SERVICE", "emanuel")

class EmanuelAction:

    @staticmethod
    async def execute(action: EmanuelActions, interaction: discord.Interaction) -> str:
        try:
            match action:
                case EmanuelActions.INTERRUPT:
                    client = Client(os.getenv("MCP_SERVER_URL"))
                    async with client:
                        try:
                            await client.call_tool("interrupt_image_generation", {})
                            return "🛑 Bildgenerierung abgebrochen"
                        except Exception as e:
                            return f"❌ Ausnahmefehler: {str(e)}"

                case EmanuelActions.UNLOAD_COMFY:
                    client = Client(os.getenv("MCP_SERVER_URL"))
                    async with client:
                        try:
                            await client.call_tool("free_image_generation_vram", {})
                            return "✅ Modelle werden entladen"
                        except Exception as e:
                            return f"❌ Ausnahmefehler: {str(e)}"

                case EmanuelActions.RESET:
                    await interaction.channel.send("Manuel Schmanuel")
                    return "✅ Emanuel hat alles vergessen"

                case EmanuelActions.START | EmanuelActions.STOP | EmanuelActions.RESTART:
                    result = subprocess.run(
                        ["sudo", "service", WORKER_SERVICE, action.value],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    if result.returncode == 0:
                        return f"✅ {action.name} erfolgreich ausgeführt."
                    else:
                        return f"❌ Fehler:\n```\n{result.stderr}\n```"

                case _:
                    raise Exception("Unbekannte Aktion")

        except Exception as e:
            print(traceback.format_exc())
            return f"❌ Abrakadabra-Ausnahmefehler: {str(e)}"
