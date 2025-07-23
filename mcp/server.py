import base64
import random
import signal
import socket
import subprocess
import time
from enum import Enum
from typing import List, LiteralString, Literal, Dict, Annotated

import fastmcp
import requests
import torch
from steam import SteamQuery
from mcstatus import JavaServer

from mcp.types import ImageContent
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
    """Gibt Online Status mit Spieleranzahl an, startet, stoppt oder startet Game-Server neu.
Server:
 - Minecraft Vanilla: mathis.party:25565
 - Minecraft Drehmal: mathis.party:25566
 - Enshrouded: Dynamisch
 """

    output: List[str] = []

    for server in servers:
        if operation == "status":

            result = subprocess.run(
                ['systemctl', 'is-active', server],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip() == "active":
                output.append(f"{server}: {_get_extended_server_info(server)}")
            else:
                output.append(f"{server} ist offline")

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

def _get_extended_server_info(server: Literal["enshrouded", "minecraft_vanilla", "minecraft_drehmal"]) -> Dict:
    domain, port = _get_server_address(server)

    if server == "enshrouded":
        server_obj = SteamQuery(domain, port)
        return_dictionary = server_obj.query_server_info()
        return {
            "address": f"{domain}:{port}",
            "name": return_dictionary.get("name", "unbekannt"),
            "online": f"{return_dictionary.get("players")}/{return_dictionary.get("max_players")}"
        }

    if server.startswith("minecraft_"):
        server_obj = JavaServer.lookup(f"{domain}:{port}")
        status = server_obj.status()
        return {
            "version": status.version.name,
            "description": status.description,
            "online": "niemand" if status.players.online == 0 else ", ".join([name.name for name in status.players.sample])
        }


def _get_server_address(server: Literal["minecraft_vanilla", "minecraft_drehmal", "enshrouded"]) -> (str, int):
    domain = "mathis.party"
    if server == "enshrouded":
        domain = socket.gethostbyname(domain)
        port = 15637
    elif server == "minecraft_vanilla":
        port = 25565
    elif server == "minecraft_drehmal":
        port = 25566
    else:
        raise Exception("Unknown Server")

    return domain, port


@mcp.tool()
def update_enshrouded_server() -> str:
    """Updated den Enshrouded Server"""

    cmd = (
        "sudo service enshrouded stop && "
        "sudo /usr/games/steamcmd "
        "+@sSteamCmdForcePlatformType windows "
        "+force_install_dir /mnt/samsung/enshrouded-server "
        "+login anonymous +app_update 2278520 +quit" #&& "
        #"sudo service enshrouded start"
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


@mcp.tool()
def call_police(message: str) -> str:
    """Ruft die Polizei, ratsam bei schweren Regelverstößen oder kriminellem Verhalten"""
    return f"Du hast die Polizei gerufen und ihr die Nachricht überbracht: {message}"


@mcp.tool()
def generate_image(prompt: str) -> fastmcp.Image:
    """Generiert ein Bild basierend auf einem Prompt"""

    with open("forge_stdout.log", "w") as out, open("forge_stderr.log", "w") as err:
        process = subprocess.Popen(
            ["stable-diffusion-webui-forge/venv/bin/python", "stable-diffusion-webui-forge/launch.py", "--api", "--listen", "--nowebui"],
            stdout=out,
            stderr=err,
            text=True
        )

        print("WebUI gestartet, warte 10 Sekunden...")
        time.sleep(13)

        try:
            url = "http://localhost:7861/sdapi/v1/txt2img"

            payload = {
                "prompt": prompt,
                "steps": 4,
                "width": 512,
                "height": 512,
                "cfg_scale": 1,
                "distilled_cfg_scale": 3.5,
                "sampler_name": "Euler",
                "scheduler": "Simple"
            }

            response = requests.post(url, json=payload)
            response.raise_for_status()  # optional: Fehler werfen bei HTTP-Fehler

            r = response.json()
            image_base64 = r["images"][0]
            image_bytes = base64.b64decode(image_base64)
            return fastmcp.Image(
                data=image_bytes,
                format="png",
            )

        finally:
            print("Beende WebUI...")
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()



# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )