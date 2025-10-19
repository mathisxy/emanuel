import asyncio
import base64
import json
import logging
import os
from typing import Literal, Annotated, Dict

from fastmcp import Context
from fastmcp.utilities.types import Image

from mcp_server.tools.comfy.comfy_ui import ComfyUIProgress, ComfyUI, ComfyUIEvent, ComfyUIImage
from mcp_server.mcp_instance import mcp


@mcp.tool(tags={"Image"})
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
        with open(os.path.join("mcp_server", "comfy-ui", f"{model}.json"), "r") as file:
            workflow = json.load(file)

        logging.debug(workflow)

        workflow["6"]["inputs"]["text"] = image_generation_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["5"]["inputs"]["height"] = height
        workflow["5"]["inputs"]["width"] = width

        #await ctx.info("Verbinden mit ComfyUI...")

        return await _comfyui_generate_image(comfy, ctx, workflow, timeout)


    finally:
        await asyncio.sleep(1)
        comfy.free_models()

@mcp.tool(tags={"Comfy Image"})
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
        with open(os.path.join("mcp_server", "comfy-ui", f"{model}.json"), "r") as file:
            workflow = json.load(file)

        logging.debug(workflow)

        workflow["6"]["inputs"]["text"] = image_generation_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["24"]["inputs"]["guidance"] = guidance

        await comfy.connect()

        with open(f"../downloads/{input_image}", "rb") as f:
            image_bytes = f.read()
            upload_image_name = comfy.upload_image(image_bytes)
            workflow["16"]["inputs"]["image"] = upload_image_name


        #await ctx.info("Verbinden mit ComfyUI...")

        return await _comfyui_generate_image(comfy, ctx, workflow, timeout)

    finally:
        await asyncio.sleep(1)
        comfy.free_models()


@mcp.tool(tags={"Comfy Image"})
async def remove_image_background(
        ctx: Context,
        image: Annotated[str, "Exakten Dateinamen angeben"],
        model: Literal["RMBG-2.0"],
        sensitivity: Annotated[float, "Wert zwischen 0.0 und 1.0"] = 1.0,
        mask_blur: int = 0,
        mask_offset: int = 0,
        invert_output: bool = False,
        refine_foreground: bool = True,
        #background: Literal["Alpha", "Color"] = "Alpha",
        #background_color: Literal["black", "white", "red", "green", "blue"] = "black",
        timeout: Annotated[int, "Sekunden"] = 30,
) -> Image:
    """Hintergrundentfernungstool: Entfernt den Hintergrund des übergebenen Bildes"""

    if not 0.0 <= sensitivity <= 1.0:
        raise ValueError("Sensitivity muss zwischen 0.0 und 1.0 liegen.")


    comfy = ComfyUI()

    try:
        with open(os.path.join("mcp_server", "comfy-ui", f"{model}.json"), "r") as file:
            workflow = json.load(file)

        logging.debug(workflow)

        # 1. RMBG Node finden
        rmbg_node_id = None
        for node_id, node in workflow.items():
            if node.get("class_type") == "RMBG":
                rmbg_node_id = node_id
                break

        if not rmbg_node_id:
            raise ValueError("RMBG-Node nicht im Workflow gefunden!")


        process_res: int = 1920 # max

        # 2. Parameter updaten
        rmbg_node = workflow[rmbg_node_id]
        rmbg_node["inputs"]["model"] = model
        rmbg_node["inputs"]["sensitivity"] = sensitivity
        rmbg_node["inputs"]["process_res"] = process_res
        rmbg_node["inputs"]["mask_blur"] = mask_blur
        rmbg_node["inputs"]["mask_offset"] = mask_offset
        rmbg_node["inputs"]["invert_output"] = invert_output
        rmbg_node["inputs"]["refine_foreground"] = refine_foreground
        rmbg_node["inputs"]["background"] = "Alpha" # background

        # 3. Farbe setzen (wenn Color gewählt)
        # if background == "Color":
        #     # Finde passende Color-Node, die mit "background_color" verbunden ist
        #     for node_id, node in workflow.items():
        #         if node.get("class_type") == "ColorInput":
        #             if "color" in node.get("inputs", {}):
        #                 node["inputs"]["color"] = background_color
        #                 break

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
        logging.info("Returning None")
        return None

    return Image(
        data=comfyui_image.image_bytes,
        format="png",
    )