import json
import random
import socket
import subprocess
from enum import Enum
from typing import List, LiteralString, Literal, Dict, Annotated

import fastmcp
import requests
from steam import SteamQuery
from mcstatus import JavaServer
from fastmcp import FastMCP
from comfy_ui import ComfyUI

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



def _free_models(including_execution_cache=False):
    url = "http://localhost:8188/free"  # Passe Host und Port ggf. an

    payload = {
        "unload_models": True,
    }

    if including_execution_cache:
        payload["free_memory"] = True

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Modelle wurden erfolgreich entladen.")
        else:
            print(f"❌ Fehler beim Entladen: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Ausnahme beim API-Aufruf: {e}")

@mcp.tool()
async def generate_image_from_reference_image(
        model: Literal["FLUX.1-kontext-Q6"],
        reference_image: Annotated[str, "Referenzbild, exakten Dateinamen angeben"],
        prompt: str,
        seed: int=207522777251329,
        guidance: Annotated[float, "Kleinerer Wert erlaubt mehr Kreativität"] = 3.5,
        timeout: Annotated[int, "Sekunden"] = 300,
) -> fastmcp.Image:
    """Generiert ein Bild auf Grundlage des Referenzbildes und des Text-Prompts.
    Dieses Tool ermöglicht Bildbearbeitung des Referenzbildes per Prompt"""

    try:
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        workflow["6"]["inputs"]["text"] = prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["24"]["inputs"]["guidance"] = guidance

        comfy = ComfyUI()
        await comfy.connect()

        with open(f"../downloads/{reference_image}", "rb") as f:
            image_bytes = f.read()
            upload_image_name = comfy.upload_image(image_bytes)
            print(upload_image_name)
            workflow["16"]["inputs"]["image"] = upload_image_name

        image_bytes = await comfy.queue(workflow, timeout=timeout)
        await comfy.close()

        return fastmcp.Image(
            data=image_bytes,
            format="png",
        )

    finally:
        _free_models()

@mcp.tool()
async def generate_image(
        model: Literal["FLUX.1-schnell-Q6", "FLUX.1-dev-Q6"],
        prompt: str,
        height: int = 512,
        width: int = 512,
        seed: int=207522777251329,
        timeout: Annotated[int, "Sekunden"] = 300,
) -> fastmcp.Image:
    """Generiert ein Bild AUSSCHLIEßLICH auf Grundlage des Text-Prompts.
    Dieses Tool hat keinen Zugriff auf Referenzbilder!"""

    try:
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        workflow["6"]["inputs"]["text"] = prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["5"]["inputs"]["height"] = height
        workflow["5"]["inputs"]["width"] = width

        comfy = ComfyUI()
        await comfy.connect()
        image_bytes = await comfy.queue(workflow, timeout=timeout)
        await comfy.close()

        return fastmcp.Image(
            data=image_bytes,
            format="png",
        )

    finally:
        _free_models()


# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )