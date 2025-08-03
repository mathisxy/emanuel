import asyncio
import io
import json
import uuid
from dataclasses import dataclass
from typing import Dict

import requests
import websockets
from websockets import ConnectionClosed
from PIL import Image
from enum import IntEnum



@dataclass
class ComfyUIEvent:
    pass

@dataclass
class ComfyUIProgress(ComfyUIEvent):
    current: float
    total: float

@dataclass
class ComfyUIImage(ComfyUIEvent):
    image_bytes: bytes
    type = "png"

class ComfyUIMessageType(IntEnum):
    PREVIEW = 1
    FINAL = 2

class ComfyUI:
    def __init__(self, domain: str = '127.0.0.1:8188', http_prefix="http://"):
        self.domain = domain
        self.http_prefix = http_prefix
        self.client_id = str(uuid.uuid4())
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect(
            f"ws://{self.domain}/ws?clientId={self.client_id}",
            max_size=20 * 1024 * 1024  # 20MB
        )

    def upload_image(self, image: bytes) -> str:
        buffer = io.BytesIO(image)
        image_format = Image.open(buffer).format.lower()
        buffer.seek(0)
        response = requests.post(
            f"{self.http_prefix}{self.domain}/upload/image",
            files={"image": (f"upload.{image_format}", buffer, f"image/{image_format}")}
        )
        response.raise_for_status()
        return response.json()["name"]

    async def queue(self, prompt: Dict[str, str], timeout: float =120, events: asyncio.Queue[ComfyUIEvent|None]|None = None) -> bytes:
        prompt_id = str(uuid.uuid4())
        p = {
            "prompt": prompt,
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }

        requests.post(f"{self.http_prefix}{self.domain}/prompt", json=p)

        try:
            async with asyncio.timeout(timeout):

                while True:
                    out = await self.ws.recv()

                    if isinstance(out, str):
                        msg = json.loads(out)
                        print("Status:", msg)

                        if msg.get("type") == "progress":
                            current = float(msg["data"]["value"])
                            total = float(msg["data"]["max"])

                            if events:
                                await events.put(ComfyUIProgress(current, total))

                        if msg.get("type") == "execution_error":
                            raise RuntimeError(f"ComfyUI execution error: {msg.get('data').get('exception_message')}")

                        if msg.get("type") == "execution_interrupted":
                            raise RuntimeError(f"Die Bildgenerierung wurde unterbrochen vom Nutzer")

                    else:
                        print("BINÄRDATEN")
                        print(f"HEADER: {out[:8]}")
                        image_bytes = out[8:]
                        header_type = int.from_bytes(out[4:8], byteorder='big')
                        if header_type == ComfyUIMessageType.PREVIEW:
                            if events:
                                await events.put(ComfyUIImage(image_bytes=image_bytes))
                        elif header_type == ComfyUIMessageType.FINAL:
                            if events:
                                await events.put(None)
                            return image_bytes

        except asyncio.TimeoutError:
            raise TimeoutError("Timed out waiting for ComfyUI response.")
        except ConnectionClosed as e:
            raise ConnectionError(f"WebSocket connection closed: {e}")
        except Exception as e:
            raise RuntimeError(str(e))

    def interrupt(self):
        response = requests.post(f"{self.http_prefix}{self.domain}/interrupt")

        response.raise_for_status()


    def free_models(self, including_execution_cache=False):
        url = f"{self.http_prefix}{self.domain}/free"

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

    async def close(self):
        await self.ws.close()