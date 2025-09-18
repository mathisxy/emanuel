import asyncio
import base64
import json
import os
import random
import socket
import subprocess
from typing import List, Literal, Dict, Annotated

from fastmcp.utilities.types import Image, Audio
from steam import SteamQuery
from mcstatus import JavaServer
from fastmcp import FastMCP, Context

from comfy_ui import ComfyUI
from comfy_ui import ComfyUIEvent, ComfyUIProgress
from comfy_ui import ComfyUIImage

# FastMCP Server initialisieren
mcp = FastMCP("game_servers")

# class Servers(Enum):
#     minecraft = "minecraft_vanilla",
#     drehmal = "minecraft_drehmal",
#     enshrouded = "enshrouded",

# class ServerOperations(Enum):
#     status = "status",
#     start = "start",
#     stop = "stop",
#     restart = "restart"

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
        servers: List[Literal["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun", "enshrouded"]],
        operation: Literal["status", "start", "stop", "restart"]
) -> List[str]:
    """
Game-Server Funktionen:
 - Online Status mit Serveradresse, Servername und Spieleranzahl abrufen
 - starten
 - stoppen
 - neustarten

Server:
 - Minecraft Vanilla
 - Minecraft Drehmal
 - Minecraft Speedrun
 - Enshrouded
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

def _get_extended_server_info(server: Literal["enshrouded", "minecraft_vanilla", "minecraft_speedrun", "minecraft_drehmal"]) -> Dict:
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


def _get_server_address(server: Literal["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun", "enshrouded"]) -> (str, int):
    domain = "mathis.party"
    if server == "enshrouded":
        domain = socket.gethostbyname(domain)
        port = 15637
    elif server == "minecraft_vanilla":
        port = 25567
    elif server == "minecraft_drehmal":
        port = 25566
    elif server == "minecraft_speedrun":
        port = 25565
    else:
        raise Exception("Unbekannter Server")

    return domain, port


@mcp.tool
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

@mcp.tool
def reset_minecraft_speedrun_server() -> str:
    """Löscht den Minecraft Speedrun Server und erstellt einen neuen"""

    path = "/mnt/samsung/speedrun/" # os.getenv("MINECRAFT_SPEEDRUN_PATH")
    url = "https://piston-data.mojang.com/v1/objects/6bce4ef400e4efaa63a13d5e6f6b500be969ef81/server.jar" # os.getenv("MINECRAFT_JAR_URL")

    subprocess.run(
        ["sudo", "service", "minecraft_speedrun", "stop"],
        capture_output=True,
        text=True,
        timeout=10
    )

    subprocess.run(
        ["rm", "-rf", path],
        capture_output=True, text=True
    )

    subprocess.run(["mkdir", "-p", path], check=True)
    subprocess.run(["sudo", "chown", "minecraft", path], check=True)

    subprocess.run(["wget", "-O", f"{path}/server.jar", url], check=True)

    with open(f"{path}/eula.txt", "w") as f:
        f.write("eula=true\n")

    subprocess.run(["sudo", "service", "minecraft_speedrun", "start"], check=True)

    return "Der Minecraft Speedrun Server wurde resettet"


@mcp.tool
def call_police(message: str) -> str:
    """Ruft die Polizei, ratsam bei schweren Regelverstößen oder kriminellem Verhalten"""
    return f"Du hast die Polizei gerufen und ihr die Nachricht überbracht: {message}" #TODO Wirft einen Fehler

@mcp.tool
async def generate_image(
        ctx: Context,
        model: Literal["FLUX.1-schnell-Q6", "FLUX.1-krea-dev-Q6"],
        image_generation_prompt: str,
        width: int = 512,
        height: int = 512,
        seed: int=207522777251329,
        timeout: Annotated[int, "Sekunden"] = 300,
) -> Image:
    """Bildgenerierungstool: Generiert ein Bild ausschließlich auf Grundlage des übergebenen Text-Prompts.
    Dieses Tool kann vorherige Bilder nicht sehen!"""

    #raise Exception("Das ist ein Test Fehler, bitte sag es dem user wenn du ihn siehst")

    if width <= 0 or height <= 0:
        raise Exception("Parameter width und height müssen größer sein als 0")

    comfy = ComfyUI()

    try:
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        workflow["6"]["inputs"]["text"] = image_generation_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["5"]["inputs"]["height"] = height
        workflow["5"]["inputs"]["width"] = width

        #await ctx.info("Verbinden mit ComfyUI...")

        return await _comfyui_generate_image(comfy, ctx, workflow, timeout)


    finally:
        await asyncio.sleep(1)
        comfy.free_models()

@mcp.tool
async def edit_image(
        ctx: Context,
        input_image: Annotated[str, "Exakten Dateinamen angeben"],
        model: Literal["FLUX.1-kontext-Q6"],
        image_generation_prompt: str,
        seed: int=207522777251329,
        guidance: float = 2.5,
        timeout: Annotated[int, "Sekunden"] = 300,
) -> Image:
    """Bildbearbeitungstool: Generiert ein neues Bild auf Grundlage des übergebenen Bildes und des Text-Prompts"""

    comfy = ComfyUI()

    try:
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        workflow["6"]["inputs"]["text"] = image_generation_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["24"]["inputs"]["guidance"] = guidance

        await comfy.connect()

        with open(f"../downloads/{input_image}", "rb") as f:
            image_bytes = f.read()
            upload_image_name = comfy.upload_image(image_bytes)
            print(upload_image_name)
            workflow["16"]["inputs"]["image"] = upload_image_name


        #await ctx.info("Verbinden mit ComfyUI...")

        return await _comfyui_generate_image(comfy, ctx, workflow, timeout)

    finally:
        await asyncio.sleep(1)
        comfy.free_models()


@mcp.tool
async def remove_image_background(
        ctx: Context,
        image: Annotated[str, "Exakten Dateinamen angeben"],
        model: Literal["RMBG-2.0"],
        sensitivity: float = 1.0,
        process_res: int = 1024,
        mask_blur: int = 0,
        mask_offset: int = 0,
        invert_output: bool = False,
        refine_foreground: bool = False,
        background: Literal["Alpha", "Color"] = "Alpha",
        background_color: Literal["black", "white", "red", "green", "blue"] = "black",
        timeout: Annotated[int, "Sekunden"] = 30,
) -> Image:
    """Hintergrundentfernungstool: Entfernt den Hintergrund des übergebenen Bildes"""


    comfy = ComfyUI()

    try:
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        # 1. RMBG Node finden
        rmbg_node_id = None
        for node_id, node in workflow.items():
            if node.get("class_type") == "RMBG":
                rmbg_node_id = node_id
                break

        if not rmbg_node_id:
            raise ValueError("RMBG-Node nicht im Workflow gefunden!")

        # 2. Parameter updaten
        rmbg_node = workflow[rmbg_node_id]
        rmbg_node["inputs"]["model"] = model
        rmbg_node["inputs"]["sensitivity"] = sensitivity
        rmbg_node["inputs"]["process_res"] = process_res
        rmbg_node["inputs"]["mask_blur"] = mask_blur
        rmbg_node["inputs"]["mask_offset"] = mask_offset
        rmbg_node["inputs"]["invert_output"] = invert_output
        rmbg_node["inputs"]["refine_foreground"] = refine_foreground
        rmbg_node["inputs"]["background"] = background

        # 3. Farbe setzen (wenn Color gewählt)
        if background == "Color":
            # Finde passende Color-Node, die mit "background_color" verbunden ist
            for node_id, node in workflow.items():
                if node.get("class_type") == "ColorInput":
                    if "color" in node.get("inputs", {}):
                        node["inputs"]["color"] = background_color
                        break

        load_image_node_id = None
        for node_id, node in workflow.items():
            if node.get("class_type") == "LoadImage":
                load_image_node_id = node_id
                break

        if not load_image_node_id:
            raise ValueError("LoadImage-Node nicht im Workflow gefunden!")


        with open(f"../downloads/{image}", "rb") as f:
            image_bytes = f.read()
            upload_image_name = comfy.upload_image(image_bytes)
            print(upload_image_name)
            load_image_node = workflow[load_image_node_id]
            load_image_node["inputs"]["image"] = upload_image_name

        await comfy.connect()

        return await _comfyui_generate_image(comfy, ctx, workflow, timeout)

    finally:
        await asyncio.sleep(1)
        comfy.free_models(including_execution_cache=True)



async def _comfyui_generate_image(comfy: ComfyUI, ctx: Context, workflow: Dict, timeout: int) -> Image|None:

    queue = asyncio.Queue[ComfyUIEvent|None]()

    async def listener(queue: asyncio.Queue[ComfyUIEvent|None]):
        while True:
            event = await queue.get()
            if event is None:
                break
            if isinstance(event, ComfyUIProgress):
                await ctx.report_progress(event.current, event.total)
            if isinstance(event, ComfyUIImage):
                await ctx.info(message="preview_image", extra={
                    "base64": base64.b64encode(event.image_bytes).decode('utf-8'),
                    "type": "png",
                })



    await comfy.connect()

    await asyncio.sleep(1) # Für VRAM

    task1 = asyncio.create_task(comfy.queue(workflow, timeout, queue))
    task2 = asyncio.create_task(listener(queue))

    #await ctx.info(f"Bild wird generiert...")
    comfyui_image, _ = await asyncio.gather(task1, task2)

    await comfy.close()

    if comfyui_image is None:
        print("Returning None")
        return None

    return Image(
        data=comfyui_image.image_bytes,
        format="png",
    )

@mcp.tool
async def generate_audio(
        ctx: Context,
        model: Literal["ACE-Step-V1-3.5B"],
        tags: Annotated[str, "Genres oder Adjektive"],
        songtext: Annotated[str, "Nutze Tags wie [instrumental] und [chorus] zur Gliederung"] = "",
        seconds: Annotated[float, "maximal 180"] = 120,
        seed: int = 207522777251329,
        #steps: Annotated[int, "im Normalfall belassen"] = 50,
        #cfg: Annotated[float, "im Normalfall belassen"] = 5.0,
        #lyrics_strength: Annotated[float, "im Normalfall belassen"]  = 0.99,
        timeout: Annotated[int, "Sekunden"] = 300,
) -> Audio:
    """Audiogenerierungstool: Generiert eine Audiodatei auf Grundlage von Tags und optionalem Songtext"""

    comfy = ComfyUI()

    try:
        # Audio-Workflow laden (basierend auf dem Screenshot)
        with open(f"comfy-ui/{model}.json", "r") as file:
            workflow = json.load(file)

        print(workflow)

        # Node 14 → Tags & Lyrics
        workflow["14"]["inputs"]["tags"] = tags
        workflow["14"]["inputs"]["lyrics"] = songtext
        #workflow["14"]["inputs"]["lyrics_strength"] = lyrics_strength

        # Node 17 → Sekunden
        workflow["17"]["inputs"]["seconds"] = seconds

        # Node 52 → Seed, Steps, CFG
        workflow["52"]["inputs"]["seed"] = seed
        #workflow["52"]["inputs"]["steps"] = steps
        #workflow["52"]["inputs"]["cfg"] = cfg

        result = await _comfyui_generate_audio(comfy, ctx, workflow, timeout)
        print(result is None)
        return result

    except FileNotFoundError:
        raise Exception(f"Audio-Workflow-Datei für Modell {model} nicht gefunden. Erwartet: comfy-ui/{model}.json")
    except Exception as e:
        raise Exception(f"Fehler bei der Audio-Generierung: {str(e)}")
    finally:
        await asyncio.sleep(1)
        comfy.free_models(including_execution_cache=True)


async def _comfyui_generate_audio(comfy: ComfyUI, ctx: Context, workflow: Dict, timeout: int) -> Audio|None:
    """Hilfsfunktion für die Audio-Generierung mit ComfyUI"""

    queue = asyncio.Queue[ComfyUIEvent|None]()

    async def listener(queue: asyncio.Queue[ComfyUIEvent|None]):
        while True:
            event = await queue.get()
            if event is None:
                break
            if isinstance(event, ComfyUIProgress):
                await ctx.report_progress(event.current, event.total)

    await comfy.connect()
    await asyncio.sleep(1)  # Für VRAM

    task1 = asyncio.create_task(comfy.queue(workflow, timeout, queue))
    task2 = asyncio.create_task(listener(queue))

    #await ctx.info(f"Audio wird generiert...")
    comfyui_audio, _ = await asyncio.gather(task1, task2)

    await comfy.close()

    if comfyui_audio is None:
        print("Returning None")
        return None

    return Audio(
        data=comfyui_audio.audio_bytes,
        format=comfyui_audio.audio_type,
    )


@mcp.tool
async def free_image_generation_vram(including_execution_cache: bool = True) -> bool:

    ComfyUI().free_models(including_execution_cache)

    await asyncio.sleep(1)

    return True


@mcp.tool
async def interrupt_image_generation() -> bool:
    #raise Exception("Test")
    comfy = ComfyUI()

    comfy.interrupt()

    await asyncio.sleep(1)

    comfy.free_models()

    return True

# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )
