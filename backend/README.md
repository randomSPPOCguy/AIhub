# AIHub Python Backend

Unified Python backend with AI models, Wikipedia, MusicBrainz, and WebSocket support.

---

## 🚀 Quick Start

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure (Optional)
Create `.env` file:
```bash
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
CLAUDE_API_KEY=your_key
```

### Run Server
```bash
python -m uvicorn main:app --port 8000

# Or with auto-reload:
python -m uvicorn main:app --reload --port 8000
```

---

## 📦 Features

### AI Providers
- **Phi-3** (local) - Loads on startup
- **OpenAI** - Cloud API
- **Claude** - Cloud API
- **Gemini** - Cloud API

### Music APIs
- **Wikipedia** - Song/artist/album information
- **MusicBrainz** - Music database lookups

### Real-time
- **WebSocket** - Room event handler

---

## 🔌 API Endpoints

**Interactive docs:** http://localhost:8000/docs

### Health
- `GET /health`
- `GET /api/health`

### Chat
- `POST /api/local_chat` - Phi-3
- `POST /api/chat` - Cloud providers

### Wikipedia
- `GET /api/wiki/song/{title}?artist=name`
- `GET /api/wiki/artist/{name}`
- `GET /api/wiki/album/{title}?artist=name`
- `GET /api/wiki/search?q=query`

### MusicBrainz
- `GET /api/mb/artist/{name}`
- `GET /api/mb/recording?title=x&artist=y`
- `GET /api/mb/artist/{id}/genres`
- `GET /api/mb/artist/{id}/discography`

### WebSocket
- `WS /ws/room`

---

## 🧪 Testing

```bash
# Direct service test
python test_wiki_direct.py

# Full API test (server must be running)
python test_new_apis.py
```

---

## 📁 Structure

```
python/
├── main.py                  # FastAPI app
├── config.py                # Settings
├── requirements.txt         # Dependencies
│
├── providers/               # AI providers
│   ├── phi3_provider.py     # Phi-3 local
│   ├── openai_provider.py   # OpenAI
│   ├── claude_provider.py   # Claude
│   └── gemini_provider.py   # Gemini
│
├── services/                # External APIs
│   ├── wikipedia_service.py
│   └── musicbrainz_service.py
│
├── websocket/               # WebSocket handlers
│   └── room_handler.py
│
└── tools/                   # Tool integrations
    └── tools_api.py
```

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# AI Provider Keys
GEMINI_API_KEY=
OPENAI_API_KEY=
CLAUDE_API_KEY=

# Local Models
LOCAL_PHI3_MODELS=microsoft/Phi-3-mini-4k-instruct

# Wikipedia/MusicBrainz User-Agent
WIKI_UA_APP=AIHub
WIKI_UA_VERSION=2.0
WIKI_UA_CONTACT=your-email@example.com

MB_UA_APP=AIHub
MB_UA_VERSION=2.0
MB_UA_CONTACT=your-email@example.com

# Bot Settings
BOT_KEYWORDS=bot,b0t,@bot,ai
DEFAULT_HISTORY_LIMIT=12
```

---

## 📊 Dependencies

**Core:**
- fastapi
- uvicorn
- pydantic
- pydantic-settings

**AI Models:**
- transformers (Phi-3)
- torch
- accelerate
- google-generativeai (Gemini)
- openai
- anthropic (Claude)

**APIs:**
- httpx (Wikipedia & MusicBrainz)
- aiohttp

**Utilities:**
- python-dotenv
- sentencepiece

---

## 🎯 Port

**Default:** 8000

Change with:
```bash
python -m uvicorn main:app --port YOUR_PORT
```

---

## 📖 More Info

See parent directory documentation:
- `../QUICK-START.md`
- `../MIGRATION-COMPLETE.md`
- `../SUCCESS-REPORT.md`

---

**Status:** ✅ Production Ready
