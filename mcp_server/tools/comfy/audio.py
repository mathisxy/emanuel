import asyncio
import json
import logging
import os.path
from typing import Dict, Annotated, Literal

from fastmcp import Context
from fastmcp.utilities.types import Audio

from mcp_server.mcp_instance import mcp
from mcp_server.tools.comfy.comfy_ui import ComfyUIProgress, ComfyUIEvent, ComfyUI


@mcp.tool(tags={"Audio"})
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
        with open(os.path.join("mcp_server", "comfy-ui", f"{model}.json"), "r") as file:
            workflow = json.load(file)

        logging.debug(workflow)

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
        logging.info("Returning None")
        return None

    return Audio(
        data=comfyui_audio.audio_bytes,
        format=comfyui_audio.audio_type,
    )