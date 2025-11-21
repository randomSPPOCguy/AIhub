# AIhub 1.4.1 - Project Frank (Experimental)

> **Project Frank**: An experimental AI enrichment system that uses the best programming language for each feature. Currently focused on real-time music knowledge enrichment with comprehensive Wikipedia/Wikidata/MusicBrainz integration.

AIhub is a unified AI hub for music knowledge enrichment, chat, and model management with intelligent context-aware responses.

## Quick Start

**Start everything with one command:**
```powershell
.\start.ps1
```

This will:
- Start Python ONNX AI Server (port 8000)
- Start Python Enrichment Service (port 8001)
- Start Node.js AIhub Server (port 3000)
- Launch the interactive console

## Project Structure

- `src/` - Main Node.js application code
- `python_ai/` - Python ONNX runtime server
- `python_enrichment/` - Python enrichment service (Wikipedia/MusicBrainz)
- `docs/` - Documentation
- `config.env` - Configuration (copy from `config.env.example`)

## Key Features

- **Centralized Logging** - All services use unified logger (`src/utils/logger.js`)
- **Enrichment Service** - Automatic keyword extraction and enrichment for user queries
- **Music Knowledge** - Wikipedia and MusicBrainz integration
- **Model Management** - Support for cloud and local models
- **Interactive CLI** - Built-in command console

## Configuration

See `docs/CONFIG_ENV.md` for environment variables.

Key settings:
- `ENRICHMENT_ENABLED=true` - Enable enrichment service
- `LOG_LEVEL=info` - Set log level (error, warn, info, debug)
- `LOG_FILE=logs/aihub.log` - Enable file logging

## Documentation

All documentation is in the `docs/` folder:
- `docs/QUICK_START.md` - Getting started guide
- `docs/COMMON_ISSUES.md` - **Troubleshooting & common problems**
- `docs/CONFIG_ENV.md` - Configuration reference
- `docs/TROUBLESHOOTING_CUDA.md` - CUDA/cuDNN setup guide
- `docs/PROJECT_NAVIGATION.md` - Codebase overview
- `docs/LOGGER_IMPLEMENTATION_STATUS.md` - Logger system details

**Project Root:**
- `SECURITY_AUDIT.md` - Security audit report
- `CLAUDE_CODE_REVIEW.md` - Review instructions for Claude Code CLI

## Project Frank - Experimental Goals

**Objective:** Build an AI system that provides rich, authoritative, real-time information about music (artists, albums, songs, genres) with sub-3-second response times.

**Current Focus:**
1. ✅ Full Wikipedia article content extraction (not just summaries)
2. 🔄 Comprehensive Wikidata integration (in progress)
3. 🔄 Persistent SQLite enrichment cache (planned)
4. 🔄 Sub-3-second response time (requires architecture decision)

**Technology Stack (Best-in-class for each layer):**
- **Core Server:** Node.js (Express) - excellent for API routing and real-time
- **Enrichment Service:** Python (FastAPI) - optimal for Wikipedia/MusicBrainz APIs
- **AI Inference:** Python (ONNX Runtime) OR Cloud API (OpenAI/Anthropic)
- **Database:** SQLite - fast, embedded, perfect for caching
- **Cache:** In-memory + SQLite persistent cache

## Current Status

**Working:**
- ✅ Centralized logging system
- ✅ Full Wikipedia article content extraction
- ✅ MusicBrainz → Wikidata → Wikipedia enrichment pipeline
- ✅ Context-aware conversation with 13-second timeout
- ✅ Artist, album, and track enrichment

**In Progress:**
- 🔄 Comprehensive Wikidata entity linking
- 🔄 SQLite persistent enrichment cache
- 🔄 Proactive information sharing
- 🔄 Response time optimization (see `PERFORMANCE_OPTIONS.md`)

**Known Issues:**
- ⚠️ Response time currently 11-12s (ONNX model bottleneck)
- ⚠️ Cache not persistent (lost on restart)
- ⚠️ Limited album/track detail retrieval

See `ISSUES.md` for full list and `PERFORMANCE_OPTIONS.md` for architecture decisions.

## Troubleshooting

**Having issues?** Start here:
- `docs/COMMON_ISSUES.md` - Quick fixes for common problems
- `docs/TROUBLESHOOTING_CUDA.md` - CUDA/GPU setup issues
- `docs/ISSUES.md` - Known bugs and technical issues

Common problems:
- Services won't start → Check ports aren't in use
- Python dependencies fail → Use virtual environments
- CUDA errors → See CUDA troubleshooting guide
- Enrichment not working → Verify service is running on port 8001

