# AIhub Models Directory

This directory is for storing local AI models used by AIhub.

## Model Search Locations

AIhub automatically searches for models in the following locations (in order):

1. **Project directory**: `./models/downloads/` (this directory)
2. **User home directory**: `~/.aihub/models/` or `%USERPROFILE%/.aihub/models/`
3. **Windows Public folder** (if exists): `C:\Users\Public\AIhub\Models\`
4. **Linux/Mac system locations** (if exists): `/usr/local/share/aihub/models/` or `/opt/aihub/models/`

## Model Directory Structure

Place your model folders here. For example:

```
models/downloads/
├── phi-3-mini-onnx-cuda/
│   ├── cpu-int4-rtn-block-32/
│   │   ├── phi3-mini-4k-instruct-cpu-int4-rtn-block-32.onnx
│   │   ├── tokenizer.json
│   │   └── ...
│   ├── cuda/
│   │   └── cuda-int4-rtn-block-32/
│   │       └── ...
│   └── genai_config.json
└── another-model/
    └── ...
```

## Migrating Existing Models

If you have models in another location (like `C:\Users\Public\AIhub\Models`), you can:

1. **Option 1 (Recommended)**: Move or copy the model folders here
   ```bash
   # Windows (PowerShell)
   Copy-Item -Recurse "C:\Users\Public\AIhub\Models\*" ".\models\downloads\"

   # Linux/Mac
   cp -r /path/to/old/models/* ./models/downloads/
   ```

2. **Option 2**: Update `config.env` to point to your existing location
   ```env
   MODEL_DOWNLOAD_DIR=C:\Users\Public\AIhub\Models
   PYTHON_MODEL_ROOT=C:\Users\Public\AIhub\Models
   ```
   Note: This ties the installation to a specific path and won't work for other users.

3. **Option 3**: Do nothing - AIhub will automatically detect models in the Windows Public folder if they exist there

## Downloading Models

Models can be downloaded from:
- Hugging Face: https://huggingface.co/models
- ONNX Model Zoo: https://github.com/onnx/models

For ONNX Runtime GenAI models, look for models that include `genai_config.json` and `.onnx` files.

## Configuration

You can configure the model search behavior in `config.env`:

```env
# Model download directory (relative paths work!)
MODEL_DOWNLOAD_DIR=./models/downloads

# Python AI model root (usually same as above)
PYTHON_MODEL_ROOT=./models/downloads

# Select which model to use
LOCAL_MODEL_NAME=phi-3-mini-onnx-cuda
LOCAL_MODEL_KIND=onnx-genai
```

## Hardware Acceleration

The system automatically detects:
- **CUDA availability**: Prefers CUDA-optimized models if CUDA is available
- **CPU fallback**: Uses CPU-optimized models if CUDA is not available

You don't need to configure this manually - it's automatic!
