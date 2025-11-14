# AI Hub Backend - Terminal Testing

This is a simplified, terminal-only setup for testing your AI Hub backend without any UI/Electron components.

## Files Included

- `backend_tester.py` - Main testing script with interactive menu
- `api_client.py` - API client for testing endpoints once server is running
- `AIhubAPP/backend/` - Your backend code

## Quick Start

### 1. Install Dependencies

```bash
cd AIhubAPP/backend
pip install -r requirements.txt --break-system-packages
```

### 2. Run the Backend Tester

```bash
python backend_tester.py
```

This will show you an interactive menu with options:
1. Generate and test API keys
2. Check dependencies
3. Test backend imports
4. Start backend server
5. Do all checks and start server
6. Exit

### 3. Test the API (In Another Terminal)

Once the server is running, open a new terminal and run:

```bash
python api_client.py
```

This will let you test various API endpoints like:
- `/health` - Check server status
- `/providers` - List available AI providers
- `/api/generate-key` - Generate new API keys
- `/chat` - Send chat messages
- `/models` - List models
- `/conversations` - List conversations

## Manual Testing

### Generate an API Key

```bash
cd AIhubAPP/backend
python generate_api_key.py
```

This will generate 3 API keys with the `jpnohub-` prefix.

### Start the Server Manually

```bash
cd AIhubAPP/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Test Endpoints with curl

```bash
# Health check
curl http://localhost:8000/health

# Get providers
curl http://localhost:8000/providers

# Generate API key (may require existing key)
curl -X POST http://localhost:8000/api/generate-key \
  -H "X-API-Key: your-api-key-here"

# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "provider": "gemini",
    "message": "Hello!",
    "conversation_id": "test-123",
    "stream": false
  }'
```

## Configuration

### Environment Variables

Create or edit `AIhubAPP/backend/.env`:

```env
# API Keys for AI Providers
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-claude-key

# Hub API Key (generated with generate_api_key.py)
BOT_API_KEY=jpnohub-your-generated-key

# Optional
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

## What's Different from the Full App?

This setup **removes**:
- ❌ Electron/Desktop UI
- ❌ React/TypeScript frontend
- ❌ Complex build process
- ❌ Node.js dependencies

This setup **keeps**:
- ✅ FastAPI backend
- ✅ All AI providers (Gemini, OpenAI, Claude)
- ✅ API key generation with `jpnohub-` prefix
- ✅ Model management
- ✅ Conversation history
- ✅ WebSocket support
- ✅ All backend services

## Testing Workflow

1. **Run the backend tester**: `python backend_tester.py`
   - Option 5 to run all checks and start server

2. **In a new terminal, run the API client**: `python api_client.py`
   - Test individual endpoints
   - Or run all tests at once

3. **Check the API**: Visit http://localhost:8000/docs for interactive API documentation

## Troubleshooting

### Import Errors
Make sure you're in the right directory and have installed all dependencies:
```bash
cd AIhubAPP/backend
pip install -r requirements.txt --break-system-packages
```

### Port Already in Use
If port 8000 is busy, you can change it:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Missing API Keys
Some features require API keys from the providers. Add them to `.env`:
- Gemini: https://makersuite.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys
- Claude: https://console.anthropic.com/

### ONNX/GPU Warnings
These are optional. The app works without ONNX/GPU support. If you see warnings, you can safely ignore them unless you specifically need local model support.

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Next Steps

- Add your provider API keys to `.env`
- Test the `/chat` endpoint with different providers
- Explore the model management features
- Check out the `/docs` endpoint for full API reference
