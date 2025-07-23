import requests
import base64


# API Endpoint
url = "http://localhost:7861/sdapi/v1/txt2img"

payload = {
    "prompt": "a cat",
    "steps": 4,
    "width": 512,
    "height": 512,
    "cfg_scale": 1,
    "distilled_cfg_scale": 3.5,
    "sampler_name": "Euler",
    "scheduler": "Simple"
}

response = requests.post(url, json=payload)
result = response.json()

print(result)
# Bild speichern
image_data = base64.b64decode(result['images'][0])
with open('output.png', 'wb') as f:
    f.write(image_data)