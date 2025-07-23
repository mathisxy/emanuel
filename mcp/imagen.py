import torch
from diffusers import DiffusionPipeline

pipe = DiffusionPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.float8_e4m3fn,
    low_cpu_mem_usage=True,
    use_safetensors=True,
)

pipe.enable_attention_slicing()

pipe.unet.to("cuda")
pipe.vae.to("cuda")
pipe.text_encoder.to("cuda")

prompt = "Astronaut in a jungle, cold color palette, muted colors, detailed"
image = pipe(prompt, height=256, width=256, num_inference_steps=20).images[0]

# Bild speichern
image.save("flux-schnell.png")
