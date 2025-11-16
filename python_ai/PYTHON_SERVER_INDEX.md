# Python ONNX AI Server

This directory contains the Python ONNX AI server components for AIhub.

## Directory Structure

- `scripts/` - Server management scripts
- `docs/` - Documentation related to the Python server

## Key Files

- `server.py` - The main ONNX server implementation
- `requirements.txt` - Python dependencies for the server
- `config.env` - Environment variables shared with the Node hub

## Server Management

Use these scripts to manage the Python ONNX server:

- `start-python-server.ps1` - Start the server
- `stop-python-server.ps1` - Stop the server
- `restart-python-server.ps1` - Restart the server

## Integration

This server is called by the AIhub application when you use the `/py` command in the AIhub console.
