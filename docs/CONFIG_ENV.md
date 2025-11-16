# Config Environment Guide

This project reads settings from `config.env` in the repository root (fallback `.env` only exists for backward compatibility). Copy `config.env.example` to `config.env`, edit the values, and keep the populated file out of version control.

## Minimum Required For Local Runs
1. Leave `PORT`/`HOST` as-is unless you need a different port.
2. Decide whether `/hub/*` should require an API key via `AIHUB_REQUIRE_KEY` (default `true`). Generate a key with `npm run keygen`.
3. Pick a local runtime:
   - For ONNX via the Python helper: set `LOCAL_MODEL_KIND=onnx-genai`, `LOCAL_MODEL_URL=http://localhost:8000`, and make sure `PYTHON_AI_*` values match the helper.
   - For Ollama/OpenAI-compatible servers: set `LOCAL_MODEL_KIND` plus `LOCAL_MODEL_URL` and optional `LOCAL_MODEL_API_KEY`.
4. Provide any cloud API keys you plan to expose in `/models` (leave blank to hide that provider).

Everything else can stay at the defaults until you integrate with Discogs/Wikipedia/MusicBrainz or need to fine-tune harvesting.

## Service & Networking
- `PORT`, `HOST`, and `AIHUB_BASE_URL` control how Express listens and which base URL is logged or shared with CLI helpers. Use `AIHUB_WS_BASE_URL` for a custom WebSocket origin or `AIHUB_INTERNAL_BASE_URL` when the CLI should hit a different loopback address.
- `MODEL_DOWNLOAD_DIR` points at the folder where catalog downloads land and where the CLI scans for artifacts.

## Behavior & Security
- `BOT_KEYWORDS`, `BOT_BEHAVIOR_PROMPT`, and `BOT_BEHAVIOR_PROMPT_FILE` define how the chat workflow identifies and steers the assistant. Keep the prompt text in this file or point to an external text file that is ignored by git.
- `HUGGINGFACE_TOKEN` gates catalog entries that require Hugging Face auth. The CLI will warn if you try to download those entries without a token.
- `AIHUB_PATH_APPEND` / `CUDA_PATH_APPEND` are optional semicolon-delimited additions to `PATH` when the CLI launches `python_ai/server.py`, which helps Windows find CUDA DLLs.

## Python Helper & Local Models
- `PYTHON_MODEL_ROOT`, `PYTHON_AI_BASE`, `PYTHON_AI_HOST`, and `PYTHON_AI_PORT` must match the values used by `python_ai/server.py`. The helper now loads the same `config.env`, so editing in one place keeps Node and Python aligned.
- `LOCAL_MODEL_*` controls how `/hub/chat` forwards OpenAI-style requests to Ollama, ONNX, or other custom runtimes.

## External Metadata Providers
Set `WIKI_UA`, `WIKIMEDIA_USER_AGENT`, `DISCOGS_TOKEN`, and the MusicBrainz UA trio (`MB_UA_APP`, `MB_UA_VERSION`, `MB_UA_CONTACT`) to comply with API policies. Optional knobs like `MB_SLEEP_MS`, `MB_RG_*`, `HARVEST_CAA`, and `SUMMARY_CONCURRENCY` let you throttle or tweak harvesting.

Keep actual secrets (API keys, tokens, download paths, hostnames) in `config.env` only. Never add real tokens or hardware-specific paths to this repository.
