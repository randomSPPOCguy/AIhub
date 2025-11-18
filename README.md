# AIhub 1.4.1 - Experimental Branch (AIhub-exp0.0.1)

AIhub is a unified AI hub for music knowledge enrichment, chat, and model management.

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

## Current Status

This is an experimental branch with:
- ✅ Centralized logging system implemented
- ✅ Enrichment service integration
- ✅ Band members and album credits enrichers
- ✅ Music response formatters
- ⚠️ Some known issues documented (see below)

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

