import asyncio
import time

import pynvml

def check_free_vram(required_gb:float=8):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Nur GPU 0
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    free_gb = info.free / 1024**3
    if free_gb < required_gb:
        raise RuntimeError(f"Nicht genug VRAM: {free_gb:.2f} GB frei, {required_gb} GB benötigt")
    print(f"Genug VRAM vorhanden: {free_gb:.2f} GB frei")

async def wait_for_vram(required_gb:float=8, timeout:float=20, interval:float=1):

    start = time.time()

    while True:
        try:
            check_free_vram(required_gb=required_gb)
            break
        except RuntimeError as e:
            if (time.time() - start) >= timeout:
                raise TimeoutError(f"Timeout: {e}")
            else:
                await asyncio.sleep(interval)