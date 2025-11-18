@echo off
echo Downloading Phi-3 Mini ONNX CUDA model...
echo This will download about 2.5GB

python -m huggingface_hub.commands.huggingface_cli download microsoft/Phi-3-mini-4k-instruct-onnx --include "cuda/cuda-int4-rtn-block-32/*" --local-dir models\downloads\phi-3-mini-onnx-cuda --local-dir-use-symlinks False

echo.
echo Done! Checking files...
dir /s models\downloads\phi-3-mini-onnx-cuda\*.onnx*

pause
