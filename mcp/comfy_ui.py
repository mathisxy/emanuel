import asyncio
import io
import json
import uuid
from typing import Dict, Annotated

import PIL
import requests
import websockets
from websockets import ConnectionClosed
from PIL import Image

class ComfyUI:
    def __init__(self, domain: str = '127.0.0.1:8188'):
        self.domain = domain
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
            f"http://{self.domain}/upload/image",
            files={"image": (f"upload.{image_format}", buffer, f"image/{image_format}")}
        )
        response.raise_for_status()
        return response.json()["name"]

    async def queue(self, prompt: Dict[str, str], timeout: float =120) -> bytes:
        prompt_id = str(uuid.uuid4())
        p = {
            "prompt": prompt,
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }

        requests.post(f"http://{self.domain}/prompt", json=p)

        try:
            async with asyncio.timeout(timeout):  # Python 3.11+
                while True:
                    out = await self.ws.recv()

                    if isinstance(out, str):
                        msg = json.loads(out)
                        print("Status:", msg)

                        if msg.get("type") == "execution_error":
                            raise RuntimeError(f"ComfyUI execution error: {msg}")

                        if msg.get("type") == "execution_success" and msg["data"].get("prompt_id") == prompt_id:
                            raise RuntimeError("Execution finished but no image was received.")

                    else:
                        # Binärdaten (vermutlich Bild)
                        print("BINÄRDATEN")
                        image_bytes = out[8:]  # Skip header
                        return image_bytes
        except asyncio.TimeoutError:
            raise TimeoutError("Timed out waiting for ComfyUI response.")
        except ConnectionClosed as e:
            raise ConnectionError(f"WebSocket connection closed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    async def close(self):
        await self.ws.close()