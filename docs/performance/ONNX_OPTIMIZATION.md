# ONNX Runtime Optimization (Future Enhancement)

## Overview

For **5-10x performance improvement**, consider switching from `transformers` (PyTorch) to `onnxruntime-genai-cuda` with CUDA acceleration.

## Current Performance

- **Transformers (CPU)**: ~5-12 tokens/second
- **Transformers (GPU)**: ~20-40 tokens/second
- **ONNX Runtime CUDA (INT4)**: ~50-100 tokens/second ⚡

## Installation

```bash
# Uninstall old versions
pip uninstall onnxruntime onnxruntime-gpu

# Install CUDA-enabled ONNX Runtime GenAI
pip install --pre onnxruntime-genai-cuda
```

## Download ONNX Model

```bash
# Install huggingface-cli if needed
pip install huggingface-hub

# Download Phi-3 ONNX CUDA model
huggingface-cli download microsoft/Phi-3-mini-4k-instruct-onnx \
  --include cuda/cuda-int4-rtn-block-32/* \
  --local-dir ./models/phi3-onnx
```

## Code Changes Required

Replace the model loading in `python/ai_gateway.py`:

```python
import onnxruntime_genai as og

# Global model (replaces transformers)
_onnx_model = None
_onnx_tokenizer = None

def _initialize_model():
    global _onnx_model, _onnx_tokenizer
    if _onnx_model is not None:
        return
    
    model_path = "models/phi3-onnx/cuda/cuda-int4-rtn-block-32"
    _onnx_model = og.Model(model_path)
    _onnx_tokenizer = og.Tokenizer(_onnx_model)

def _generate_with_phi3(prompt: str, max_tokens: int = 128) -> str:
    _initialize_model()
    
    if _onnx_model is None:
        return "[ONNX model not available]"
    
    tokens = _onnx_tokenizer.encode(prompt)
    params = og.GeneratorParams(_onnx_model)
    params.set_search_options(max_length=max_tokens, temperature=0.7, top_p=0.9)
    params.input_ids = tokens
    
    generator = og.Generator(_onnx_model, params)
    
    # Generate
    while not generator.is_done():
        generator.compute_logits()
        generator.generate_next_token()
    
    output_tokens = generator.get_sequence(0)
    return _onnx_tokenizer.decode(output_tokens)
```

## Performance Gains

- **Current (CPU)**: 2 minutes per response
- **With ONNX CUDA**: ~5-10 seconds per response
- **Speedup**: 10-20x faster

## Requirements

- NVIDIA GPU with CUDA support
- CUDA toolkit installed
- ~2GB VRAM for INT4 quantized model

## References

- [ONNX Runtime GenAI Docs](https://onnxruntime.ai/docs/genai/)
- [Phi-3 ONNX Tutorial](https://onnxruntime.ai/docs/genai/tutorials/phi3-python.html)
- [Model Download](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-onnx)

