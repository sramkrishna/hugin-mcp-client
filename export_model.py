#!/usr/bin/env python3.13
"""Export Qwen 2.5 Coder to OpenVINO format with INT8 quantization."""

import sys
from pathlib import Path

try:
    from optimum.intel import OVModelForCausalLM
    from transformers import AutoTokenizer
    print("✓ Imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

model_id = "Qwen/Qwen2.5-Coder-3B-Instruct"
output_dir = Path.home() / "models" / "qwen2.5-coder-3b-openvino"

print(f"\nExporting {model_id} to OpenVINO IR format...")
print(f"Output directory: {output_dir}")
print(f"Quantization: INT8 (optimized for NPU)")
print("\nThis will download ~6GB and take 10-15 minutes...\n")

try:
    # Export model with INT8 quantization for NPU
    print("Step 1/3: Downloading and converting model...")
    model = OVModelForCausalLM.from_pretrained(
        model_id,
        export=True,
        compile=False,  # Don't compile yet, we'll do that at runtime
        load_in_8bit=True,  # INT8 quantization for NPU
    )

    print("Step 2/3: Saving model...")
    model.save_pretrained(output_dir)

    print("Step 3/3: Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.save_pretrained(output_dir)

    print(f"\n✓ Export complete! Model saved to: {output_dir}")
    print("\nModel files:")
    for f in sorted(output_dir.iterdir()):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name:40s} {size_mb:8.1f} MB")

except Exception as e:
    print(f"\n✗ Export failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
