import asyncio

from mcp_server.mcp_instance import mcp
from comfy_ui import ComfyUI


@mcp.tool(tags={"Comfy Control"})
async def free_image_generation_vram(including_execution_cache: bool = True) -> bool:

    ComfyUI().free_models(including_execution_cache)

    await asyncio.sleep(1)

    return True


@mcp.tool(tags={"Comfy Control"})
async def interrupt_image_generation() -> bool:
    #raise Exception("Test")
    comfy = ComfyUI()

    comfy.interrupt()

    await asyncio.sleep(1)

    comfy.free_models()

    return True