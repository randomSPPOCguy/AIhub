# Python ONNX GenAI Server - Quick Start

## Scripts Available

### Start Server
```powershell
.\python_ai\start-python-server.ps1
```
Starts the Python server with GPU support. Press `Ctrl+C` to stop.

### Stop Server
```powershell
.\python_ai\stop-python-server.ps1
```
Gracefully stops the Python server process(es).

### Restart Server
```powershell
.\python_ai\restart-python-server.ps1
```
Stops and restarts the server.

### Force Kill Server
```powershell
.\python_ai\kill-python-server.ps1
```
Force kills all Python processes (use if server won't stop normally).

## Quick Commands (Manual)

### Start
```powershell
cd python_ai
.\.venv\Scripts\Activate.ps1
python server.py
```

### Stop (in same terminal)
Press `Ctrl+C`

### Stop (from another terminal)
```powershell
# Find and kill Python server process
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*python_ai*" } | Stop-Process -Force

# Or kill anything using port 8000
$proc = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($proc) { Stop-Process -Id $proc.OwningProcess -Force }
```

### Check if running
```powershell
# Check health endpoint (replace with your PYTHON_AI_BASE if customized)
Invoke-WebRequest -Uri http://localhost:8000/api/health -UseBasicParsing | Select-Object -ExpandProperty Content

# Or check processes
Get-Process python -ErrorAction SilentlyContinue

# Or check port
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

## Server Endpoints

- **Health**: `${PYTHON_AI_BASE}/api/health` (defaults to `http://localhost:8000`)
- **Chat**: `${PYTHON_AI_BASE}/api/chat`
- **Models**: `${PYTHON_AI_BASE}/api/models`
- **Local Chat (alias)**: `${PYTHON_AI_BASE}/api/local_chat`
- **Local Models (alias)**: `${PYTHON_AI_BASE}/api/local_models`

## Environment Variables

Configure these keys in `config.env` (see `/docs/CONFIG_ENV.md`):

- `PYTHON_AI_HOST=0.0.0.0` - Server host
- `PYTHON_AI_PORT=8000` - Server port  
- `PYTHON_AI_BASE=http://localhost:8000` - Base URL used by the Node proxy
- `PYTHON_MODEL_ROOT=./models/downloads` - Model directory
- `PYTHON_AI_BIN` / `PYTHON` - Optional overrides for the Python interpreter

## Notes

- Make sure the virtual environment is activated before running `python server.py`
- The server will use CUDA if available (check `/api/health` to confirm)
- Models are cached in memory after first load

