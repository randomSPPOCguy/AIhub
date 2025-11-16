# AI Hub 1.4.1

Local-first harvesting hub for music-sharing rooms. It ingests **song-ended** events, normalizes genres, and harvests metadata from Wikipedia, Discogs, and MusicBrainz (with optional Cover Art). It stores a compact **facts** record per play in SQLite and exposes a tiny REST API for your main LLM (e.g., Gemini) to answer instantly from local data.

## Why 1.4.1 (what's new vs 1.0)
- Pluggable genre map using Discogs **Style** + Wikipedia **title** for API-friendly lookups.
- Clean ingest endpoint (`POST /ingest/song-ended`) with schema validation.
- Provider helpers for Wikipedia REST Summary + Title Search; Discogs Database Search; MusicBrainz Release-Group album count (1 r/s compliant).
- Optional Cover Art Archive pull using MusicBrainz IDs.
- REST API to fetch recent plays and harvested facts (`/api/facts/latest`, `/api/facts/by-artist`, `/api/plays/recent`, `/api/genres`).

## Quick start
```bash
cp config.env.example config.env
npm install
npm run migrate
npm start
```

Update the newly created `config.env` using the descriptions in `docs/CONFIG_ENV.md` before starting the services.

### ONNX Runtime GenAI microservice
To run CUDA/ONNX models locally, start the Python helper in a second terminal:
```bash
cd python_ai
python -m venv .venv
. .venv/Scripts/activate    # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python server.py            # listens on http://0.0.0.0:8000
```
Once `npm start` is running you can also type `py` inside the `hub>` console to launch the same helper without leaving that terminal (it will auto-prefer `python_ai/.venv` if present).
Set `LOCAL_MODEL_KIND=onnx-genai`, `LOCAL_MODEL_URL=http://localhost:8000`, and optionally `PYTHON_MODEL_ROOT=./models/downloads` so the Node hub proxies requests through `PYTHON_AI_BASE`.

### Built-in hub console
Running `npm start` (or `start.ps1`) now prints your detected CPU/GPU and opens an interactive `hub>` prompt right in the same terminal. Type `help` to list commands:
- `models` / `overview` – show hardware plus both cloud + local inventories.
- `local` / `cloud` – drill into each section (installed runtimes, downloads, or cloud providers).
- `select <id>` – switch models (same as `/models set ...`).
- `download <#|id>` - kick off a numbered catalog download (uses `/api/models/download` under the hood; run `local` first to refresh the list).
- `py` / `python` - start the ONNX Runtime Python helper within the same `hub>` console once your models/tooling are ready.
- `tooling` - print CUDA / ONNX Runtime / PyTorch install commands tailored to your GPU.
- `onboard` – re-run the setup wizard after you add new tooling.
- `keygen [label]` – generate a hub API key without leaving the console.
- `active`, `clear`, `exit` – convenience helpers while the same server keeps running.
- First launch runs a short **setup wizard** that checks ONNX Runtime GenAI + CUDA + PyTorch, then offers to download the best ONNX CUDA model for your GPU (you can skip and use `download` later).
- First launch runs a short **setup wizard** that points you at ONNX Runtime, CUDA, and PyTorch installs, then lets you opt-in to downloading the recommended local model for your hardware (skip anytime and re-run via `tooling` + manual `download`).

### CUDA / ONNX local runtimes
- The `/local` command now highlights ONNX + CUDA-ready builds (e.g., `Phi-3 Mini 4K Instruct (ONNX INT4)`), including copy/paste download commands.
- After downloading, point a local ONNX runtime (e.g., `onnxruntime-gpu` with `--providers cuda`) at the model and set `LOCAL_MODEL_URL`/`LOCAL_MODEL_KIND=onnx-genai` to proxy through the hub.
- GGUF entries remain available for llama.cpp/Ollama, so you can mix CUDA ONNX deployments with CPU/GGUF ones.
- Need more options? Drop additional JSON snippets under `models/catalog.d/*.json` (same schema as `models/catalog.json`) and `/local` will merge them live every time you open the command.

### Generate an API key for providers
AI runtime endpoints require a JavaAIHub API key (unless `AIHUB_REQUIRE_KEY=false`). Generate one from the terminal:

```bash
npm run keygen -- --label "my-test-client"
```

Copy the token immediately; it will not be shown again. Use it via `X-AIHub-Key` or `Authorization: Bearer`.

### Test locally
Use a REST client or `curl` to send a song-ended event:
```bash
curl -X POST http://localhost:7071/ingest/song-ended   -H "Content-Type: application/json"   -d '{
    "roomId":"a75a...ba04",
    "username":"demo_user",
    "userId":"user-demo-123",
    "artist":"Massive Attack",
    "title":"Teardrop",
    "album":"Mezzanine",
    "year":1998,
    "genre":"trip hop",
    "eventId":"evt-001"
  }'
```

Then query the latest facts:
```bash
curl http://localhost:7071/api/facts/latest
```

## Env notes
- **Wikipedia**: set a real `WIKI_UA` (User-Agent). Uses REST Summary and Core Title Search.
- **Discogs**: set `DISCOGS_TOKEN`, requests sent with `Authorization: Discogs token=...`.
- **MusicBrainz**: set `MB_UA_*` and respect 1 request/second. We throttle automatically.
- **Cover Art**: set `HARVEST_CAA=true` to fetch cover art via Cover Art Archive using MBIDs.
- **AI providers**: configure `OPENAI_*`, `ANTHROPIC_*`, `GOOGLE_*`, `HUGGINGFACE_*` and `LOCAL_MODEL_*` env vars (or the alias keys like `CLAUDE_API_KEY` / `DEFAULT_*`) to unlock each backend. Only providers with valid API keys are shown in `/models`; downloaded local runtimes are listed automatically.
- **ONNX Runtime service**: `PYTHON_AI_BASE`, `PYTHON_AI_PORT`, and `PYTHON_MODEL_ROOT` control the Python microservice that hosts ONNX GenAI models.
- **Security**: `AIHUB_REQUIRE_KEY=true` enforces API-key auth for `/hub/*`, `/models/*`, and `/api/models/*`.

## Endpoints
- `POST /ingest/song-ended` — store a play & harvest metadata.
- `GET  /api/facts/latest` — most recent play + harvested facts.
- `GET  /api/facts/by-artist?name=...` – last facts row for an artist (case-insensitive).
- `GET  /api/plays/recent?limit=20` – latest N plays.
- `GET  /api/genres` – the canonical genre/style/title mapping used for harvest hints.
- `POST /hub/chat` – OpenAI-style JSON payload routed to the currently selected provider/local runtime.
- `POST /hub/chat` with user content `/model`, `/models`, `/local`, or `/cloud` – returns the hardware-aware inventory (overview/local/cloud) and supports `/models <id>` or `/models set <id>` to switch instantly.
- `GET /models` – API view of the overview payload; `/models/local` and `/models/cloud` expose each subsection directly.
- `POST /models/select { "id": "openai:gpt-4o-mini" }` – update the runtime selection from scripts or CI.
- `GET /api/models/catalog` – curated download catalog (includes Microsoft Phi-3 Mini 128K).
- `POST /api/models/download` – download from the trusted catalog or provide `{ "url": "https://...", "name": "my-model" }` for any HTTPS artifact.

## Integrating with your bot
- Your external bot listens to room events. After each song finishes, POST the payload here.
- Your **local model (phi-3 mini)** can read from `facts` directly or call `GET /api/facts/*`.
- Your **main LLM** only wakes up when your chat has `BOT_KEYWORDS` present. It should call the hub first to answer from cached facts, avoiding fresh external calls.
- To proxy OpenAI-style chats through the selected provider, send:

```bash
curl -X POST http://localhost:7071/hub/chat \
  -H "Content-Type: application/json" \
  -H "X-AIHub-Key: <token>" \
  -d '{"messages":[{"role":"user","content":"Summarize Massive Attack."}]}'
```

### Switching models without restarting
- Send `/model` or `/models` inside `/hub/chat` payloads to receive a hardware-aware overview plus `/cloud` & `/local` subsections.
- Use `/model /local` (or `/local`) to see installed runtimes, download suggestions, and the latest free local model based on `models/catalog.json`.
- Use `/model /cloud` (or `/cloud`) to see cloud providers unlocked by your `config.env` keys; `/models openai:gpt-4o-mini` or `/models set local:phi-3-mini-128k-instruct` still switches inline.
- Call `GET /models`, `/models/local`, `/models/cloud`, or `POST /models/select { "id": "..." }` from automation with the hub API key to orchestrate deployments.

### Local Phi-3 Mini 128K flow
1. Download via the catalog:
   ```bash
   curl -X POST http://localhost:7071/api/models/download \
     -H "Content-Type: application/json" \
     -H "X-AIHub-Key: <token>" \
     -d '{"id":"phi-3-mini-128k-instruct-q4"}'
   ```
2. Point your local runtime (Ollama, LM Studio, llama.cpp server, etc.) at the downloaded GGUF under `./models/downloads/phi-3-mini-128k-instruct-q4/`.
3. Set `LOCAL_MODEL_URL`, `LOCAL_MODEL_KIND` (`ollama` or `openai`), and `LOCAL_MODEL_NAME` in `config.env`.
4. Switch via `/models local:phi-3-mini-128k-instruct` or the `/models/select` endpoint.

## Project layout
```
src/
  index.js               # Express app, routers, CORS, error handling
  config.js              # env parsing
  utils/
    logger.js
    rateLimit.js         # 1 r/s for MusicBrainz,
  db/
    connection.js
    migrate.js
    schema.sql
  search/
    providers.js         # wiki, discogs, musicbrainz, cover art
  harvest/
    afterPlay.js
  ingest/
    router.js            # POST /ingest/song-ended
  api/
    factsRouter.js       # read-only API for your LLM
config/
  genres.json            # API-friendly subgenres map (alt hip-hop / alt rock / minimal metal)
```

## License

This project is released under the **AIhub Non-Commercial Attribution License**.

- You may read, modify, and share the code.
- **You may not use it for commercial purposes** (no selling, no paid hosting, no monetized products built on it).
- If you reuse parts of this code, please:
  - Attribute the original project and author: `AIhub` by GitHub user `randomSPPOCguy`.
  - Briefly mention which parts you reused or adapted (for example: CLI menu system, chat routing, music knowledge integration).

See the `LICENSE` file for full details.
