import torch
from diffusers import DiffusionPipeline, OnnxStableDiffusionPipeline
from pathlib import Path
import shutil
import os

# === SETUP ===
model_id = "black-forest-labs/FLUX.1-schnell"
export_dir = Path("flux1_onnx")
quant_dir = Path("flux1_quant")

# === 1. Laden des Originalmodells ===
print("🔄 Lade FLUX.1...")
pipe = DiffusionPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.float16,  # Float16 verwenden
    use_safetensors=True,
    #variant="fp16"
)
pipe.enable_attention_slicing()

# === 2. Exportiere das Modell in ONNX ===
print("📤 Exportiere nach ONNX...")

# Diffusers erwartet separaten Export von Komponenten: UNet, VAE, TextEncoder
if export_dir.exists():
    shutil.rmtree(export_dir)
export_dir.mkdir(parents=True, exist_ok=True)

# Wir verwenden den internen Export-Helper von optimum
os.system(f"""
  optimum-cli export onnx --model {model_id} \
    --task stable-diffusion \
    --output {export_dir.as_posix()} \
    --fp16
""")

# === 3. Lade ONNX-Modell als Pipline ===
print("📦 Lade ONNX-Pipeline...")
onnx_pipe = OnnxStableDiffusionPipeline.from_pretrained(
    export_dir,
    provider="CPUExecutionProvider"
)

# === 4. Post-Training Quantisierung mit ONNXRuntime ===
print("🔧 Quantisiere mit ONNX Runtime INT8...")
from optimum.onnxruntime import ORTQuantizer, ORTQuantizationConfig

quant_config = ORTQuantizationConfig(
    per_channel=True,
    reduce_range=True,
    activation_type="uint8",
    weight_type="int8",
    optimize_model=True
)

quantizer = ORTQuantizer.from_pretrained(export_dir, feature="stable-diffusion")
quantizer.quantize(
    save_dir=quant_dir,
    quantization_config=quant_config
)

print(f"✅ Quantisierung abgeschlossen: {quant_dir}")
