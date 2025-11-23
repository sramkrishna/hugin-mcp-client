# NPU Status on Fedora 43 (Lunar Lake)

**Last Updated:** 2025-11-23
**System:** Fedora 43, Kernel 6.17.6-300.fc43.x86_64
**Hardware:** Intel Lunar Lake NPU (rev 04)

## Current Status: ⚠️ Detected but Not Functional

The NPU hardware is **detected** and has drivers installed, but **crashes during model compilation** due to Intel compute runtime compatibility issues.

### What Works ✅

- **NPU Hardware Detection**
  - `lspci`: NPU visible as `00:0b.0 Processing accelerators: Intel Corporation Lunar Lake NPU (rev 04)`
  - Device node exists: `/dev/accel0` with proper permissions

- **NPU Driver Installation**
  - Package: `intel-npu-driver-1.16.0-1.fc44.x86_64` ✓ Installed
  - Level Zero: `intel-level-zero-25.31.34666.3-1.fc43.x86_64` ✓ Installed

- **OpenVINO Detection**
  - OpenVINO 2025.1.0 successfully detects NPU
  - `Core().available_devices` returns: `['CPU', 'GPU', 'NPU']` ✓

- **CPU Inference**
  - Model compilation: ✓ Works (1.4s compile time)
  - Inference: ✓ Expected ~2-5 tok/s for 3B models (slow but functional)

### What Doesn't Work ❌

- **NPU Inference**
  - Crashes during model compilation
  - Error: `ZE_RESULT_ERROR_UNKNOWN, code 0x7ffffffe`
  - Assertion failure: `__shared_ptr_deref: __p != nullptr`

- **GPU Inference** (Same Issue!)
  - Also crashes with identical error
  - Suggests issue is with Intel compute runtime (cldnn backend)
  - Affects both GPU and NPU since they share the same backend

## Error Details

### Crash Log
```
Exception from src/plugins/intel_npu/src/compiler_adapter/src/ze_graph_ext_wrappers.cpp:362:
L0 pfnCreate2 result: ZE_RESULT_ERROR_UNKNOWN, code 0x7ffffffe
/usr/include/c++/15/bits/shared_ptr_base.h:1344:
_Tp* std::__shared_ptr_deref(_Tp*) [with _Tp = cldnn::memory]:
Assertion '__p != nullptr' failed.
```

### Warnings During Compilation
```
WARNING: ENABLE_CPU_PINNING property is not supported by this compiler version
WARNING: NPU_STEPPING property is not supported by this compiler version
WARNING: NPU_MAX_TILES property is not supported by this compiler version
WARNING: INFERENCE_PRECISION_HINT property is not supported by this compiler version
WARNING: NPU_BATCH_MODE property is not supported by this compiler version
WARNING: EXECUTION_MODE_HINT property is not supported by this compiler version
WARNING: COMPILER_DYNAMIC_QUANTIZATION property is not supported by this compiler version
WARNING: NPU_QDQ_OPTIMIZATION property is not supported by this compiler version
```

These warnings suggest a **version mismatch** between OpenVINO and the NPU compiler.

## Component Versions

| Component | Version | Status |
|-----------|---------|--------|
| OpenVINO | 2025.1.0-000-- | ✓ Installed |
| Intel NPU Driver | 1.16.0-1.fc44 | ✓ Installed |
| Intel Level Zero | 25.31.34666.3-1.fc43 | ✓ Installed |
| OneAPI Level Zero | 1.24.3-1.fc43 | ✓ Installed |
| Linux Kernel | 6.17.6-300.fc43.x86_64 | ✓ Running |
| Fedora Version | 43 | ✓ Running |

## Root Cause Analysis

The issue is **not** that NPU is unsupported on Fedora. The problem is a **compatibility bug** in the Intel compute runtime stack:

1. **Hardware**: ✓ Working (NPU detected, driver loaded)
2. **Driver**: ✓ Working (device node present, permissions correct)
3. **OpenVINO**: ✓ Working (NPU detected in device list)
4. **Runtime**: ❌ Broken (Level Zero crashes during model compilation)

The crash occurs in the `cldnn` (Compute Library for Deep Neural Networks) backend, which is shared between GPU and NPU. This explains why **both GPU and NPU crash with the same error**.

## Workarounds

### Option 1: CPU-Only (Current)
```toml
# config.toml
[llm]
provider = "openvino"
model_path = "~/models/qwen2.5-coder-3b-openvino"
device = "CPU"  # Works, but slow (~2-5 tok/s)
```

**Performance:**
- Tokens/sec: ~2-5 (slow)
- Power: ~8-15W
- Use case: Local testing only

### Option 2: Remote GPU (Recommended)
```toml
# config.toml
[llm]
provider = "openai"  # vLLM/Ollama with OpenAI API
base_url = "http://10.0.0.100:8000/v1"
model = "qwen2.5-coder-7b"
```

**Performance:**
- Tokens/sec: ~80-120 (fast)
- Power: Remote server
- Use case: Production use until NPU is fixed

### Option 3: Claude API (Fallback)
```toml
# config.toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
# ANTHROPIC_API_KEY required
```

**Performance:**
- Tokens/sec: ~40-60 (very fast)
- Cost: ~$3-15/M tokens
- Use case: Best quality, when cost is acceptable

## Expected NPU Performance (When Working)

Based on Intel's specifications and OpenVINO benchmarks for Lunar Lake NPU:

| Model Size | Expected tok/s | Power Draw | Latency (50 tokens) |
|------------|---------------|------------|---------------------|
| 3B (int4) | 20-40 | 3-5W | ~1.5-2.5s |
| 7B (int4) | 10-20 | 3-5W | ~2.5-5s |
| 7B (int8) | 8-15 | 4-6W | ~3-6s |
| Vision (4B) | 5-10 | 4-6W | ~5-10s |

**NPU Benefits (when functional):**
- ✅ 3-5W power draw (vs 20-50W GPU)
- ✅ Perfect for on-battery usage
- ✅ Silent operation (no fan noise)
- ✅ Local/private inference
- ✅ Good enough for quick queries

## Next Steps to Fix

### Short Term (Wait for Updates)
1. **Monitor Intel NPU driver updates**
   ```bash
   dnf check-update | grep intel-npu
   ```

2. **Monitor OpenVINO updates**
   ```bash
   pip list --outdated | grep openvino
   ```

3. **Monitor Level Zero updates**
   ```bash
   dnf check-update | grep level-zero
   ```

### Medium Term (Try Different Versions)
1. **Try OpenVINO 2025.0** (older, might be more stable)
   ```bash
   pip install openvino==2025.0
   ```

2. **Try OpenVINO nightly** (newer, might have fixes)
   ```bash
   pip install --pre openvino --extra-index-url https://pypi.org/simple
   ```

3. **Try different Level Zero versions**
   - Check Intel's GitHub for newer releases
   - May need to compile from source

### Long Term (Community Support)
1. **Report bug to Intel**
   - OpenVINO GitHub: https://github.com/openvinotoolkit/openvino/issues
   - Include error log, versions, `dmesg` output

2. **Monitor Fedora bug tracker**
   - Check if others have reported this issue
   - Subscribe to relevant bugs

3. **Check Intel NPU plugin development**
   - https://github.com/openvinotoolkit/openvino_contrib/tree/master/modules/openvino_code

## Testing NPU Status

### Quick Test Script
```bash
# Test if NPU is working
python3 -c "
from openvino import Core
core = Core()
print('Devices:', core.available_devices)

try:
    model = core.compile_model('model.xml', 'NPU')
    print('✓ NPU working!')
except Exception as e:
    print('✗ NPU broken:', str(e)[:100])
"
```

### Check for Updates
```bash
# Check driver version
rpm -qa | grep intel-npu-driver

# Check for updates
sudo dnf check-update | grep -E "intel-npu|level-zero|openvino"

# Update if available
sudo dnf upgrade intel-npu-driver intel-level-zero oneapi-level-zero
```

## Related Documentation

- [OPENVINO_NPU_SETUP.md](./OPENVINO_NPU_SETUP.md) - Setup instructions (for when NPU works)
- [IMPLEMENTATION_PLAN.md](../archive/docs/IMPLEMENTATION_PLAN.md) - Archived plan with NPU strategy
- OpenVINO NPU docs: https://docs.openvino.ai/2025/openvino-workflow/inference-with-openvino/inference-devices-and-modes/npu-device.html

## Conclusion

**TL;DR:**
- NPU hardware: ✓ Detected
- NPU driver: ✓ Installed
- NPU runtime: ❌ Crashes (compatibility bug)
- CPU inference: ✓ Works (slow)
- GPU inference: ❌ Also crashes (same bug)

**Recommendation:** Use remote GPU (10.0.0.100) or Claude API until Intel fixes the compute runtime on Fedora 43.

The good news: This is a **software bug, not a hardware limitation**. Once Intel updates the Level Zero runtime or OpenVINO improves compatibility, the NPU should work as expected with excellent performance (10-40 tok/s at 3-5W).

---

**Status checks:**
- Last tested: 2025-11-23
- Next check: Weekly (monitor for driver/OpenVINO updates)
- Issue tracking: https://github.com/openvinotoolkit/openvino/issues (create if not exists)
