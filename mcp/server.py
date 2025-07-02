import random
import socket
import subprocess
from enum import Enum
from typing import List, LiteralString, Literal

from fastmcp import FastMCP

# FastMCP Server initialisieren
mcp = FastMCP("game_servers")

class Servers(Enum):
    minecraft = "minecraft_vanilla",
    drehmal = "minecraft_drehmal",
    enshrouded = "enshrouded",

class ServerOperations(Enum):
    status = "status",
    start = "start",
    stop = "stop",
    restart = "restart"

@mcp.tool()
def roll_dice(sides: int = 6) -> int:
    """Würfelt einen Würfel mit der angegebenen Seitenanzahl"""
    if sides < 2:
        raise Exception("Ein Würfel muss mindestens zwei Seiten haben")

    result = random.randint(1, sides)
    print("RESULT")
    print(result)
    return result

@mcp.tool()
def control_game_server(
        servers: List[Literal["minecraft_vanilla", "minecraft_drehmal", "enshrouded"]],
        operation: Literal["status", "start", "stop", "restart"]
) -> List[str]:
    """Gibt online Status zurück, startet, stoppt oder startet Game-Server neu.
Server:
 - Minecraft Vanilla: mathis.party:25565
 - Minecraft Drehmal: mathis.party:25566
 - Enshrouded: Dynamisch
 """

    output = []

    for server in servers:
        if operation == "status":

            result = subprocess.run(
                ['systemctl', 'is-active', server],
                capture_output=True,
                text=True,
                timeout=5
            )
            output.append(f"{server} ist online" if result.stdout.strip() == "active" else f"{server} ist offline")

        else:
            result = subprocess.run(
                ['sudo', 'service', server, operation],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output.append(f"{server} {operation} erfolgreich")
            else:
                output.append(f"{server} {operation} fehlgeschlagen: {result.stderr.strip()}")

    return output


@mcp.tool()
def get_enshrouded_server_address() -> str:
    """IPv4:Port des Enshrouded Servers, fürs manuelle Verbinden."""

    try:
        ip_address = socket.gethostbyname("mathis.party")
        return f"{ip_address}:15637"
    except socket.gaierror as e:
        return f"Fehler bei der DNS-Auflösung von mathis.party: {str(e)}"


@mcp.tool()
def update_enshrouded_server() -> str:
    """Updated den Enshrouded Server"""

    cmd = (
        "sudo service enshrouded stop && "
        "sudo /usr/games/steamcmd "
        "+@sSteamCmdForcePlatformType windows "
        "+force_install_dir /mnt/samsung/enshrouded-server "
        "+login anonymous +app_update 2278520 +quit && "
        "sudo service enshrouded start"
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 Minuten Timeout, anpassbar
        )

        if result.returncode == 0:
            return "Enshrouded Server Update wurde erfolgreich durchgeführt."
        else:
            return f"Fehler beim Update:\n{result.stderr.strip() or result.stdout.strip()}"

    except subprocess.TimeoutExpired:
        return "Timeout: Das Update hat zu lange gedauert und wurde abgebrochen."
    except Exception as e:
        return f"Fehler beim Ausführen des Updates: {str(e)}"


# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )