# Models Directory

This directory is for storing AI models used by the Python ONNX server.

## Directory Structure

- `downloads/` - Downloaded ONNX models (excluded from git)
- `catalog.json` - Model catalog configuration (if present)

## Downloading Models

Models are large files and are excluded from git. To download models:

1. Use the AIhub CLI model downloader
2. Or manually place ONNX models in `models/downloads/`

## Note

Model files (*.onnx, *.bin, *.gguf) are excluded from git via `.gitignore` due to their large size.
