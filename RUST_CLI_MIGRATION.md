# Rust CLI Migration Plan - Project Frank

**Date:** 2025-11-20
**Status:** Planning Phase
**Goal:** Replace Node.js CLI with professional Rust CLI, keep backend services

---

## 🎯 Migration Overview

### What Changes

**REMOVE:**
- ❌ `src/cli/commandConsole.js` - Node.js interactive console
- ❌ Node.js CLI dependencies (inquirer, chalk, etc.)
- ❌ Interactive terminal code from `src/index.js`

**KEEP (Backend Services):**
- ✅ Node.js HTTP server (`src/index.js` - API routes)
- ✅ Node.js WebSocket (`src/routes/roomWebSocket.js`)
- ✅ All API endpoints (`/hub/chat`, `/api/*`, etc.)
- ✅ Python ONNX server (port 8000)
- ✅ Python enrichment service (port 8001)
- ✅ SQLite database

**ADD (New Rust CLI):**
- ✨ `aihub-cli/` - New Rust project
- ✨ `aihub-cli.exe` - Compiled binary (Windows)
- ✨ `aihub-cli` - Compiled binary (Linux/Mac)

### What Users See

**Before (Current):**
```
User runs: .\start.ps1
  → PowerShell starts services
  → Launches Node.js console
  → Two different interfaces (confusing)
```

**After (Rust CLI):**
```
User runs: aihub start
  → Rust CLI starts services in background
  → Shows professional TUI interface
  → Single, consistent experience
  → Fast startup (<100ms)
```

---

## 🏗️ New Architecture

### Service Stack

```
┌─────────────────────────────────────┐
│   Rust CLI (aihub-cli.exe)          │  ← NEW: User-facing interface
│   - Interactive TUI                  │
│   - Service management               │
│   - Chat interface                   │
│   - Configuration wizard             │
└─────────────────────────────────────┘
         ▼ HTTP API calls
┌─────────────────────────────────────┐
│   Node.js Backend (HTTP Server)     │  ← KEEP: Core API
│   Port 7071                          │
│   - /hub/chat endpoint               │
│   - /api/* endpoints                 │
│   - WebSocket server                 │
│   - Enrichment client                │
└─────────────────────────────────────┘
         ▼ Service calls
┌──────────────────┬──────────────────┐
│ Python ONNX      │ Python Enrichment│  ← KEEP: Specialized services
│ Port 8000        │ Port 8001        │
│ - Model inference│ - Wikipedia      │
│ - CUDA/CPU       │ - MusicBrainz    │
│ - Phi-3          │ - Wikidata       │
└──────────────────┴──────────────────┘
         ▼ Data storage
┌─────────────────────────────────────┐
│   SQLite Database                    │  ← KEEP: Data persistence
│   ./db/music.sqlite                  │
│   - Conversation history             │
│   - Enrichment cache                 │
│   - User profiles                    │
└─────────────────────────────────────┘
```

---

## 🦀 Rust CLI Features

### Core Functionality

**1. Service Management**
- Start/stop all services (Node.js, Python ONNX, Python enrichment)
- Health checks for each service
- Auto-restart on failure
- Graceful shutdown

**2. Interactive Chat**
- Real-time chat with AI
- Chat history (scroll back)
- Context-aware responses
- Conversation timeout display

**3. Model Management**
- List available models
- Download models from HuggingFace
- Select active model
- Show model info (size, speed, requirements)

**4. Configuration**
- Interactive setup wizard (first run)
- Edit config.env values
- Hardware detection and recommendations
- Validate configuration

**5. Hardware Detection**
- Detect NVIDIA GPU (CUDA support)
- Detect AMD GPU (ROCm support)
- CPU info and recommendations
- Memory and disk space checks

**6. Terminal UI (TUI)**
- Split panes (chat + status)
- Live service status indicators
- Beautiful formatting (colors, borders, tables)
- Progress bars for downloads
- Keyboard shortcuts

---

## 🔒 Security Improvements

### Why Rust CLI Is More Secure

**1. Memory Safety**
- No buffer overflows
- No use-after-free bugs
- Compiler prevents common vulnerabilities
- Zero-cost abstractions

**2. Type Safety**
- Strong type system prevents errors
- No null pointer exceptions
- Pattern matching for error handling
- Compile-time guarantees

**3. Dependency Security**
- `cargo audit` - Check for vulnerable dependencies
- Minimal dependencies (vs Node.js 1000+ packages)
- Reproducible builds
- No npm supply chain attacks

**4. Secure Defaults**
- HTTPS by default for API calls
- API key encryption at rest
- Secure temp file handling
- Proper permission checks

**5. Sandboxing**
- Services run in isolated processes
- No shared memory vulnerabilities
- Each service has minimal permissions
- Process monitoring and limits

### Security Features to Implement

**API Key Management:**
- Store API keys encrypted (using `keyring` crate)
- Never log sensitive data
- Memory zeroization after use
- Prompt for keys, never hardcode

**Process Isolation:**
- Run Python services as separate processes
- Limit CPU/memory for each service
- Monitor for suspicious behavior
- Kill runaway processes

**Network Security:**
- Validate all HTTP responses
- Certificate pinning for cloud APIs
- Rate limiting built into CLI
- Timeout on all network calls

**File System Security:**
- Validate all file paths (prevent traversal)
- Check permissions before write
- Atomic file operations
- Secure temp directory usage

---

## 📦 Rust CLI Dependencies

### Essential Crates (Libraries)

**CLI Framework:**
- `clap` - Command-line argument parsing
  - Best CLI arg parser in any language
  - Auto-generate help text
  - Subcommands, aliases, validation

**TUI Framework:**
- `ratatui` - Terminal UI framework
  - Beautiful layouts (split panes, tabs)
  - Widgets (text, lists, tables, charts)
  - Event handling (keyboard, mouse)
  - Cross-platform terminal support

**HTTP Client:**
- `reqwest` - HTTP client
  - Async/await support
  - JSON serialization
  - TLS by default
  - Connection pooling

**JSON Handling:**
- `serde` + `serde_json` - Serialization
  - Type-safe JSON parsing
  - Automatic struct conversion
  - Error handling built-in

**Process Management:**
- `tokio` - Async runtime
  - Multi-threaded task executor
  - Process spawning and monitoring
  - Signal handling
  - Timers and timeouts

**Configuration:**
- `config` - Config file management
  - Read .env files
  - Merge multiple sources
  - Type-safe access
  - Validation

**Database (for cache):**
- `rusqlite` - SQLite bindings
  - Zero-copy reads
  - Type-safe queries
  - Connection pooling
  - Async support via `tokio-rusqlite`

**Security:**
- `keyring` - Secure credential storage
  - OS keychain integration
  - Encrypted at rest
  - Cross-platform

**Styling:**
- `crossterm` - Terminal control
  - Colors, styles, cursor movement
  - Cross-platform (Windows, Linux, Mac)
  - Mouse support

---

## 🔄 Migration Steps

### Phase 1: Setup Rust Project (Week 1)

**Day 1-2: Environment Setup**
- [ ] Install Rust: `winget install Rustlang.Rust.MSVC`
- [ ] Verify installation: `rustc --version`
- [ ] Create project: `cargo new aihub-cli --bin`
- [ ] Test build: `cd aihub-cli && cargo build`

**Day 3-4: Basic CLI Structure**
- [ ] Add `clap` dependency for commands
- [ ] Implement subcommands: `start`, `stop`, `chat`, `config`, `model`
- [ ] Add `--help` documentation
- [ ] Test command parsing

**Day 5-7: Service Management**
- [ ] Process spawning (start Node.js backend)
- [ ] Process monitoring (check if services running)
- [ ] Health check endpoints
- [ ] Graceful shutdown

### Phase 2: TUI Development (Week 2)

**Day 1-3: Basic TUI**
- [ ] Add `ratatui` + `crossterm`
- [ ] Create main layout (header, chat, status, input)
- [ ] Keyboard event handling
- [ ] Basic text rendering

**Day 4-5: Chat Interface**
- [ ] HTTP client to `/hub/chat` endpoint
- [ ] Message history scrolling
- [ ] Live typing indicator
- [ ] Error display

**Day 6-7: Status Dashboard**
- [ ] Service status indicators
- [ ] Hardware info display
- [ ] Active model display
- [ ] Conversation timeout counter

### Phase 3: Integration (Week 3)

**Day 1-3: Configuration**
- [ ] Read config.env
- [ ] Interactive config wizard
- [ ] Validate settings
- [ ] Write updated config

**Day 4-5: Model Management**
- [ ] List available models
- [ ] Download from HuggingFace
- [ ] Progress bars for downloads
- [ ] Model selection UI

**Day 6-7: Hardware Detection**
- [ ] CUDA detection (nvidia-smi)
- [ ] CPU info
- [ ] Recommendations based on hardware
- [ ] Display in TUI

### Phase 4: Cleanup (Week 4)

**Day 1-2: Remove Node.js CLI**
- [ ] Delete `src/cli/commandConsole.js`
- [ ] Remove CLI code from `src/index.js`
- [ ] Remove CLI dependencies from `package.json`
- [ ] Update `start.ps1` to use Rust CLI

**Day 3-4: Testing**
- [ ] Test all commands
- [ ] Test service startup/shutdown
- [ ] Test chat functionality
- [ ] Test on Windows, Linux, Mac

**Day 5: Documentation**
- [ ] Update README.md
- [ ] CLI usage guide
- [ ] Build instructions
- [ ] Troubleshooting

**Day 6-7: Polish**
- [ ] Error messages
- [ ] Loading animations
- [ ] Keyboard shortcuts guide
- [ ] Release build optimization

---

## 🔗 Integration Points

### How Rust CLI Talks to Services

**1. Node.js Backend (HTTP)**
```
Rust CLI → HTTP POST http://localhost:7071/hub/chat
          ← JSON response
```

**2. Service Management (Process Control)**
```
Rust CLI → spawn("node", ["src/index.js"])
         → spawn("python", ["python_ai/server.py"])
         → spawn("python", ["python_enrichment/server.py"])
```

**3. Configuration (File I/O)**
```
Rust CLI → read("config.env")
         → parse key=value pairs
         → write("config.env")
```

**4. Database (SQLite)**
```
Rust CLI → SQLite query (for cache checks)
         ← Results
```

### API Endpoints Rust CLI Needs

**Chat:**
- `POST /hub/chat` - Send message, get AI response

**Service Health:**
- `GET /health` - Node.js backend health
- `GET /api/health` - Additional health check
- `GET http://localhost:8000/health` - ONNX server
- `GET http://localhost:8001/health` - Enrichment service

**Models:**
- `GET /models` - List available models
- `POST /models/select` - Change active model
- `GET /models/active` - Get current model info

**Configuration:**
- `GET /api/config` - Get current config
- `POST /api/config` - Update config values

---

## 📁 Project Structure

### After Migration

```
AIhub/
├── aihub-cli/              ← NEW: Rust CLI project
│   ├── Cargo.toml          ← Dependencies
│   ├── Cargo.lock          ← Dependency lock
│   └── src/
│       ├── main.rs         ← Entry point
│       ├── cli.rs          ← Command definitions
│       ├── tui/            ← Terminal UI modules
│       │   ├── mod.rs
│       │   ├── app.rs      ← Main TUI app
│       │   ├── chat.rs     ← Chat widget
│       │   └── status.rs   ← Status widget
│       ├── services.rs     ← Service management
│       ├── config.rs       ← Config handling
│       ├── client.rs       ← HTTP client
│       └── models.rs       ← Model management
│
├── src/                    ← KEEP: Node.js backend
│   ├── index.js            ← Simplified (no CLI code)
│   ├── routes/             ← API routes
│   ├── services/           ← Business logic
│   └── db/                 ← Database
│
├── python_ai/              ← KEEP: ONNX server
├── python_enrichment/      ← KEEP: Enrichment service
├── db/                     ← KEEP: SQLite database
├── config.env              ← KEEP: Configuration
└── start.ps1               ← UPDATE: Launch Rust CLI
```

---

## 🚀 Startup Flow (After Migration)

### Old Flow (Current)
```
User → start.ps1
     → Start Python ONNX (port 8000)
     → Start Python enrichment (port 8001)
     → Start Node.js (port 7071)
     → Node.js launches interactive console
     → User sees Node.js CLI
```

### New Flow (Rust CLI)
```
User → aihub start
     → Rust CLI checks config
     → Spawn Python ONNX (port 8000)
     → Spawn Python enrichment (port 8001)
     → Spawn Node.js backend (port 7071)
     → Wait for health checks
     → Show TUI dashboard
     → User interacts with Rust CLI
     → Rust CLI → HTTP → Node.js → Python services
```

---

## 🎨 TUI Design (Terminal UI Layout)

### Main Screen
```
┌─────────────────────────────────────────────────────────────┐
│  AIhub v1.4.1 | Model: phi-3-mini-onnx-cuda | GPU: RTX 4060 │
├─────────────────────────────────────────────────────────────┤
│                        Chat History                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ User: What was Eminem's last album?                   │  │
│  │                                                        │  │
│  │ AI: The Death of Slim Shady (Coup de Grâce) was      │  │
│  │ released on July 12, 2024. The album features...     │  │
│  │ [11.2s]                                               │  │
│  │                                                        │  │
│  │ User: Tell me more about it                           │  │
│  │                                                        │  │
│  │ AI: The album received critical acclaim...           │  │
│  │ [Typing...]                                           │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Services: ●Node.js ●ONNX ●Enrichment | Context: 8.2s     │
├─────────────────────────────────────────────────────────────┤
│  > Your message: _                                          │
│  [Ctrl+C: Exit] [Ctrl+L: Clear] [↑↓: History]              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Commands to Implement

### Basic Commands

**`aihub start`**
- Start all services
- Launch TUI dashboard
- Monitor health

**`aihub stop`**
- Stop all services gracefully
- Clean shutdown

**`aihub chat`**
- Interactive chat mode
- Full TUI interface

**`aihub status`**
- Show service status
- Display current model
- Show hardware info

**`aihub config`**
- Interactive config editor
- Show current settings
- Validate and save

**`aihub model`**
- List available models
- Download models
- Select active model
- Show model details

**`aihub setup`**
- First-time setup wizard
- Hardware detection
- Model recommendation
- Config generation

### Advanced Commands

**`aihub logs`**
- Tail service logs
- Filter by service
- Search logs

**`aihub restart`**
- Restart specific service
- Or restart all

**`aihub update`**
- Check for CLI updates
- Update models
- Update dependencies

---

## 🎯 Success Criteria

### Migration Complete When:

- [ ] Rust CLI binary builds successfully
- [ ] All services start from Rust CLI
- [ ] Chat functionality works through TUI
- [ ] Model selection works
- [ ] Configuration wizard works
- [ ] Hardware detection works
- [ ] Service monitoring works
- [ ] Graceful shutdown works
- [ ] Cross-platform (Windows, Linux, Mac)
- [ ] Node.js CLI code removed
- [ ] Documentation updated
- [ ] User can't tell backend is still Node.js

### Quality Metrics

- Startup time: <500ms (vs current ~3s)
- Memory usage: <20MB (vs current ~100MB for Node.js console)
- Binary size: <10MB (single file)
- CPU usage: <1% idle (vs current ~5%)
- Feels professional and polished

---

## 🚨 Risks & Mitigation

### Risk 1: Learning Curve

**Risk:** Rust is harder than Node.js
**Mitigation:**
- Start with simple CLI first
- Use high-level libraries (ratatui, clap)
- Prototype in stages
- Lots of documentation and examples available

### Risk 2: Integration Issues

**Risk:** Rust CLI can't communicate with Node.js backend
**Mitigation:**
- Backend stays unchanged (proven to work)
- HTTP is language-agnostic
- Test integration early
- Fallback: keep Node.js CLI temporarily

### Risk 3: Cross-Platform Bugs

**Risk:** CLI works on Windows but not Linux
**Mitigation:**
- Use cross-platform libraries (crossterm)
- Test on all platforms early
- CI/CD for multi-platform builds

### Risk 4: Time Investment

**Risk:** Takes longer than expected
**Mitigation:**
- 4-week timeline is realistic
- Can release incrementally
- Keep old CLI as backup
- MVP first, polish later

---

## 📚 Learning Resources

### Rust Basics
- The Rust Book - https://doc.rust-lang.org/book/
- Rust by Example - https://doc.rust-lang.org/rust-by-example/
- Rustlings (exercises) - https://github.com/rust-lang/rustlings

### CLI Development
- clap tutorial - https://docs.rs/clap/latest/clap/_tutorial/
- Command Line Apps in Rust - https://rust-cli.github.io/book/

### TUI Development
- ratatui tutorial - https://ratatui.rs/tutorial/
- ratatui examples - https://github.com/ratatui-org/ratatui/tree/main/examples

### Async Rust
- Tokio tutorial - https://tokio.rs/tokio/tutorial
- Async book - https://rust-lang.github.io/async-book/

---

## 🏁 Quick Start (After Rust Install)

```powershell
# Create project
cd C:\Users\markq\antigravityAIhubEXP0.0.1\AIhub
cargo new aihub-cli --bin

# Add dependencies to Cargo.toml
cd aihub-cli
# Edit Cargo.toml, add dependencies

# Build
cargo build

# Run
cargo run -- start

# Build release (optimized)
cargo build --release
# Binary at: target/release/aihub-cli.exe
```

---

**Status:** Ready to begin
**Estimated Time:** 4 weeks for MVP
**Next Step:** Install Rust and create project structure
