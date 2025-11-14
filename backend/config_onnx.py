# ONNX Configuration
# Set USE_ONNX=True to use ONNX Runtime (faster) or False for PyTorch (default)

import os

# Toggle between PyTorch and ONNX
USE_ONNX = os.getenv("USE_ONNX", "false").lower() == "true"

# ONNX model path
ONNX_MODEL_PATH = "backend/models/phi3-onnx"

# Print current mode
if USE_ONNX:
    print("==> Using ONNX Runtime (GPU-optimized)")
else:
    print("==> Using PyTorch (default)")


