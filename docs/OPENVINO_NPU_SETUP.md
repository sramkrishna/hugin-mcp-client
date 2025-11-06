# OpenVINO NPU Setup for Lunar Lake

## Overview

Run LLMs on your Lunar Lake NPU using **OpenVINO Model Server** with an OpenAI-compatible API that Hugin can use directly.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Lunar Lake Laptop                              │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │  OpenVINO Model Server                   │  │
│  │  (OpenAI-compatible API)                 │  │
│  │                                          │  │
│  │  Endpoint: http://localhost:8000/v1     │  │
│  │  - /chat/completions (OpenAI format)    │  │
│  │  - /completions                         │  │
│  │  - Tool calling support                 │  │
│  │  - Vision model support                 │  │
│  └──────────────────────────────────────────┘  │
│                    ▼                            │
│  ┌──────────────────────────────────────────┐  │
│  │  Intel NPU (AI Boost)                    │  │
│  │  - Phi-3-Vision (vision tasks)           │  │
│  │  - Qwen 2.5 7B (text)                    │  │
│  │  - Power: 3-5W                           │  │
│  │  - Speed: 3-20 tok/s                     │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
                    ▲
                    │ HTTP API (OpenAI format)
                    │
┌─────────────────────────────────────────────────┐
│  Hugin Client                                   │
│  - Connects like to Claude/Ollama              │
│  - No code changes needed!                      │
└─────────────────────────────────────────────────┘
```

## Installation

### Option 1: Docker (Recommended)

```bash
# Pull OpenVINO Model Server image
docker pull openvino/model_server:latest

# Create directory for models
mkdir -p ~/openvino-models

# Download and convert a model (example: Phi-3-Vision)
pip install optimum-intel openvino

# Convert model to OpenVINO format
optimum-cli export openvino \
  --model microsoft/Phi-3-vision-128k-instruct \
  --weight-format int4 \
  --trust-remote-code \
  ~/openvino-models/phi3-vision

# Run model server with NPU
docker run -d \
  --device /dev/dri \
  -v ~/openvino-models:/models \
  -p 8000:8000 \
  openvino/model_server:latest \
  --rest_port 8000 \
  --model_path /models/phi3-vision \
  --model_name phi3-vision \
  --target_device NPU

# Test the server
curl http://localhost:8000/v1/models
```

### Option 2: Native Installation

```bash
# Install OpenVINO and Model Server
pip install openvino openvino-model-server

# Convert model
optimum-cli export openvino \
  --model microsoft/Phi-3-vision-128k-instruct \
  --weight-format int4 \
  ~/openvino-models/phi3-vision

# Start server
ovms \
  --rest_port 8000 \
  --model_path ~/openvino-models/phi3-vision \
  --model_name phi3-vision \
  --target_device NPU
```

## Model Conversion for NPU

### Text Models

**Qwen 2.5 7B (recommended for NPU)**
```bash
optimum-cli export openvino \
  --model Qwen/Qwen2.5-7B-Instruct \
  --weight-format int4 \
  --trust-remote-code \
  ~/openvino-models/qwen-7b

# Start server
ovms \
  --rest_port 8000 \
  --model_path ~/openvino-models/qwen-7b \
  --model_name qwen-7b \
  --target_device NPU
```

**Phi-3-mini (lighter, faster)**
```bash
optimum-cli export openvino \
  --model microsoft/Phi-3-mini-128k-instruct \
  --weight-format int4 \
  ~/openvino-models/phi3-mini

# Performance: ~20-40 tok/s on NPU
```

### Vision Models

**Phi-3-Vision (recommended)**
```bash
optimum-cli export openvino \
  --model microsoft/Phi-3-vision-128k-instruct \
  --weight-format int4 \
  --trust-remote-code \
  ~/openvino-models/phi3-vision

# Use for screenshot analysis, image queries
```

**Qwen2-VL**
```bash
optimum-cli export openvino \
  --model Qwen/Qwen2-VL-7B-Instruct \
  --weight-format int4 \
  --trust-remote-code \
  ~/openvino-models/qwen2-vl

# Better vision understanding than Phi-3
```

### Using GGUF Models (Llamafile Format!)

**NEW in 2025.2:** Load GGUF models directly!

```bash
# Download a GGUF model
wget https://huggingface.co/TheBloke/Phi-3-mini-128k-instruct-GGUF/resolve/main/phi-3-mini-128k-instruct-q4_k_m.gguf \
  -O ~/openvino-models/phi3-mini.gguf

# Start server with GGUF
ovms \
  --rest_port 8000 \
  --model_path ~/openvino-models/phi3-mini.gguf \
  --model_name phi3 \
  --target_device NPU

# That's it! No conversion needed.
```

**Benefit:** Use any llamafile-compatible model on NPU!

## Testing the Server

### Test 1: Basic Chat
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

### Test 2: Vision Query
```bash
# Base64 encode an image
IMAGE_BASE64=$(base64 -w 0 screenshot.png)

curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3-vision",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "What application is running in this screenshot?"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,'$IMAGE_BASE64'"}}
        ]
      }
    ]
  }'
```

### Test 3: Tool Calling
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-7b",
    "messages": [
      {"role": "user", "content": "What is my current CPU usage?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_system_resources",
          "description": "Get current CPU and memory usage",
          "parameters": {
            "type": "object",
            "properties": {}
          }
        }
      }
    ]
  }'
```

## Hugin Configuration

**The beauty:** Hugin already supports OpenAI-compatible APIs!

```toml
# ~/.config/hugin/llm.toml

[local_npu]
provider = "openai"  # Use OpenAI-compatible client
base_url = "http://localhost:8000/v1"
api_key = "not-needed"  # Local server, no key required
model = "phi3-vision"  # or "qwen-7b"

[routing]
# Use NPU for vision tasks
use_npu_for_vision = true
vision_model = "phi3-vision"

# Use NPU for simple text queries
use_npu_for_simple = true
text_model = "qwen-7b"
max_tokens_npu = 500  # Short responses on NPU

# Fallback to remote for complex queries
fallback_for_complex = true
fallback_provider = "vllm"  # Your 10.0.0.100 GPU
fallback_endpoint = "http://10.0.0.100:8000/v1"
```

## Performance Benchmarks

### Expected Performance on Lunar Lake NPU:

| Model | Task | Tokens/sec | Power | Latency (20 tokens) |
|-------|------|-----------|-------|---------------------|
| Phi-3-mini 3.8B | Text | 20-40 | 3-5W | ~1 sec |
| Qwen 2.5 7B | Text | 10-20 | 3-5W | ~2 sec |
| Phi-3-Vision 4.2B | Vision | 3-8 | 4-6W | ~3-5 sec |
| Qwen2-VL 7B | Vision | 5-10 | 4-6W | ~2-4 sec |

**Note:** First inference may be slower (model loading), subsequent queries are fast.

## Multi-Model Server

**Run multiple models simultaneously:**

```bash
# Create config file
cat > ~/openvino-models/config.json <<EOF
{
  "model_config_list": [
    {
      "config": {
        "name": "phi3-vision",
        "base_path": "/models/phi3-vision",
        "target_device": "NPU"
      }
    },
    {
      "config": {
        "name": "qwen-7b",
        "base_path": "/models/qwen-7b",
        "target_device": "NPU"
      }
    }
  ]
}
EOF

# Start server with multiple models
ovms \
  --rest_port 8000 \
  --config_path ~/openvino-models/config.json
```

**Then in Hugin:**
```python
# Vision query
response = client.chat.completions.create(
    model="phi3-vision",
    messages=[{"role": "user", "content": "Analyze this screenshot"}]
)

# Text query
response = client.chat.completions.create(
    model="qwen-7b",
    messages=[{"role": "user", "content": "Why is CPU high?"}]
)
```

## Intelligent Routing Example

```python
# hugin_mcp_client/llm_providers/npu_router.py

class NPURouter:
    """Smart routing between NPU, GPU, and API."""

    def __init__(self):
        self.npu = OpenAIClient(base_url="http://localhost:8000/v1")
        self.gpu = OpenAIClient(base_url="http://10.0.0.100:8000/v1")
        self.api = AnthropicClient()

    async def route(self, messages, context):
        # Vision → NPU (power efficient)
        if context.get("image"):
            return await self.npu.chat(
                model="phi3-vision",
                messages=messages
            )

        # Simple text on battery → NPU
        if self.on_battery() and len(str(messages)) < 1000:
            try:
                return await self.npu.chat(
                    model="qwen-7b",
                    messages=messages,
                    timeout=3  # Fast timeout
                )
            except TimeoutError:
                # NPU slow, fall through to GPU
                pass

        # Complex tool calling → GPU
        if context.get("tools") and len(context.tools) > 2:
            return await self.gpu.chat(
                model="qwen-72b",
                messages=messages
            )

        # Default → GPU
        return await self.gpu.chat(
            model="qwen-72b",
            messages=messages
        )
```

## Troubleshooting

### NPU Not Detected
```bash
# Check available devices
python -c "from openvino import Core; print(Core().available_devices)"

# Should show: ['CPU', 'GPU', 'NPU']

# If NPU missing:
# 1. Update to latest OpenVINO (2025.2+)
# 2. Update Intel NPU drivers
# 3. Check BIOS (NPU should be enabled)
```

### Model Loading Fails
```bash
# Check model directory
ls -lh ~/openvino-models/phi3-vision/

# Should contain:
# - openvino_model.xml
# - openvino_model.bin
# - config.json

# Re-convert if files missing
optimum-cli export openvino --model ... --weight-format int4 ...
```

### Slow Inference
```bash
# Check if actually using NPU
# Look for "NPU" in server logs

# If using CPU instead:
# - Explicitly set target_device=NPU
# - Check NPU driver installation
# - Try int8 quantization instead of int4

optimum-cli export openvino \
  --model Qwen/Qwen2.5-7B-Instruct \
  --weight-format int8 \
  ~/openvino-models/qwen-7b
```

### Tool Calling Not Working
```bash
# OpenVINO Model Server 2025.2+ required for tool calling
ovms --version

# If older version:
pip install --upgrade openvino-model-server

# Test tool calling capability:
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-7b", "messages": [...], "tools": [...]}'
```

## Systemd Service (Run on Boot)

```bash
# Create service file
sudo tee /etc/systemd/system/openvino-npu.service <<EOF
[Unit]
Description=OpenVINO Model Server with NPU
After=network.target

[Service]
Type=simple
User=$USER
Environment="HOME=/home/$USER"
ExecStart=/usr/local/bin/ovms \
  --rest_port 8000 \
  --config_path /home/$USER/openvino-models/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable openvino-npu
sudo systemctl start openvino-npu

# Check status
sudo systemctl status openvino-npu

# View logs
journalctl -u openvino-npu -f
```

## Next Steps

1. **Install OpenVINO Model Server**
   ```bash
   pip install openvino-model-server optimum-intel
   ```

2. **Convert a test model**
   ```bash
   optimum-cli export openvino \
     --model microsoft/Phi-3-mini-128k-instruct \
     --weight-format int4 \
     ~/openvino-models/phi3-mini
   ```

3. **Start server on NPU**
   ```bash
   ovms --rest_port 8000 \
     --model_path ~/openvino-models/phi3-mini \
     --model_name phi3 \
     --target_device NPU
   ```

4. **Test with curl**
   ```bash
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "phi3", "messages": [{"role": "user", "content": "Hello!"}]}'
   ```

5. **Update Hugin config**
   ```toml
   [local_npu]
   provider = "openai"
   base_url = "http://localhost:8000/v1"
   model = "phi3"
   ```

6. **Test from Hugin**
   ```bash
   hugin chat "Hello, are you running on my NPU?"
   ```

## Resources

- [OpenVINO Model Server Docs](https://docs.openvino.ai/2025/model-server/)
- [LLM Serving Guide](https://docs.openvino.ai/2025/model-server/ovms_docs_llm_reference.html)
- [NPU Support](https://docs.openvino.ai/2025/openvino-workflow/generative/inference-with-genai/inference-with-genai-on-npu.html)
- [Tool Calling](https://docs.openvino.ai/2025/model-server/ovms_docs_rest_api_chat.html)
- [GGUF Support](https://blog.openvino.ai/blog-posts/openvino-genai-supports-gguf-models)

## Summary

**OpenVINO Model Server is the llamafile-equivalent for NPU!**

✅ OpenAI-compatible API (no Hugin changes needed)
✅ NPU support (power efficient)
✅ Tool calling support (2025.2+)
✅ Vision model support (perfect for screenshots)
✅ GGUF loader (use llamafile models directly!)
✅ Multi-model serving
✅ Production-ready

**Best of all:** Hugin already speaks OpenAI API, so it works out of the box!
