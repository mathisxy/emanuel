import os
import subprocess
import traceback
from enum import Enum
from fastmcp import Client

class EmanuelAction(str, Enum):
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    INTERRUPT = "interrupt_image_generation"
    UNLOAD_COMFY = "unload_comfy_models"


WORKER_SERVICE = os.getenv("WORKER_SERVICE", "emanuel")

class EmanuelActions:

    @staticmethod
    async def execute(action: EmanuelAction) -> str:
        try:
            match action:
                case EmanuelAction.INTERRUPT:
                    client = Client(os.getenv("MCP_SERVER_URL"))
                    async with client:
                        try:
                            await client.call_tool("interrupt_image_generation", {})
                            return "🛑 Bildgenerierung abgebrochen"
                        except Exception as e:
                            return f"❌ Ausnahmefehler: {str(e)}"

                case EmanuelAction.UNLOAD_COMFY:
                    client = Client(os.getenv("MCP_SERVER_URL"))
                    async with client:
                        try:
                            await client.call_tool("free_image_generation_vram", {})
                            return "✅ Modelle werden entladen"
                        except Exception as e:
                            return f"❌ Ausnahmefehler: {str(e)}"

                case _:
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

        except Exception as e:
            print(traceback.format_exc())
            return f"❌ Abrakadabra-Ausnahmefehler: {str(e)}"
