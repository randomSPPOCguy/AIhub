# PROJECT FRANK 🦀🐍🐹⚡

> ⚠️ **WORK IN PROGRESS** - This project is under active development. Many features are incomplete or experimental.

A polyglot AI assistant framework combining Rust, Python, Go, and C++ for multi-domain query processing with intelligent enrichment and caching.

## ⚠️ Current Status

**Working:**
- ✅ Basic Rust/Python/Go/C++ FFI integration
- ✅ Build system and compilation pipeline
- ✅ SQLite caching infrastructure
- ✅ Terminal UI framework (ratatui)

**In Development / Broken:**
- ⚠️ AI model integration (placeholder implementation)
- ⚠️ MusicBrainz API integration (stub)
- ⚠️ Sports API integration (stub)
- ⚠️ Complete TUI menu system
- ⚠️ Multi-model support and selection
- ⚠️ Configuration management

## Overview

Project Frank is a unified bot foundation driven by a Rust orchestrator with embedded Python, Go, and C++ modules. It provides:

- **Multi-language Integration**: Seamlessly combines Rust (orchestration), Python (AI/NLP), Go (domain queries), and C++ (performance-critical operations)
- **Intelligent Caching**: SQLite-based caching with TTL support for enrichment data
- **Terminal UI**: Interactive TUI for real-time query processing and monitoring
- **Modular Architecture**: Clean separation of concerns across language boundaries

## Features

- 🦀 **Rust Core**: High-performance orchestration and FFI coordination
- 🐍 **Python AI Gateway**: LLM integration and natural language processing
- 🐹 **Go Domain Handlers**: Specialized query processors for music, sports, and more
- ⚡ **C++ Performance**: Fast operations for time-critical tasks
- 💾 **Smart Caching**: SQLite-based enrichment data caching with TTL
- 🖥️ **Interactive TUI**: Real-time terminal interface with ratatui

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               Rust Orchestrator (main)              │
│  - TUI (ratatui)                                    │
│  - FFI Coordination                                 │
│  - SQLite Caching                                   │
└─────────────┬───────────────┬───────────────────────┘
              │               │
    ┌─────────▼─────┐   ┌────▼──────────┐
    │  Python (PyO3) │   │  Go (CGO)     │
    │  - AI Models   │   │  - Music API  │
    │  - NLP         │   │  - Sports API │
    └────────────────┘   └───────────────┘
              │
         ┌────▼─────────┐
         │  C++ (cc)    │
         │  - Fast Ops  │
         └──────────────┘
```

## Prerequisites

> **⚠️ CRITICAL FOR WINDOWS USERS**: This project requires the **MinGW-w64 GNU toolchain**, NOT MSVC.  
> Follow all Windows-specific instructions carefully to avoid linker errors.

### Required Software

#### 1. **Rust** (1.91+)

**Windows / macOS / Linux**:
```
# Install rustup (Rust installer)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Or on Windows PowerShell:
Invoke-WebRequest -Uri https://win.rustup.rs -OutFile rustup-init.exe
.\rustup-init.exe
```

**For Windows - Install GNU Toolchain** (required):
```
# After rustup installation
rustup toolchain install stable-x86_64-pc-windows-gnu
rustup default stable-x86_64-pc-windows-gnu

# Verify
rustc --version --verbose
# Should show: host: x86_64-pc-windows-gnu
```

Sources: [rustup.rs][web:170], [Rust Install Guide][web:167]

#### 2. **Go** (1.23+)

**Download from**: https://go.dev/dl/

**Windows**:
- Download `go1.23.X.windows-amd64.msi`
- Run installer
- Verify: `go version`

**macOS**:
```
brew install go
# Or download from go.dev/dl/
```

**Linux**:
```
wget https://go.dev/dl/go1.23.X.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.23.X.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

Source: [Go Installation][web:178]

#### 3. **Python** (3.11+)

**Windows**:
```
# Download from python.org
# Or use winget:
winget install -e --id Python.Python.3.11

# ⚠️ IMPORTANT: Check "Add Python to PATH" during installation
```

**macOS**:
```
brew install python@3.11
```

**Linux**:
```
sudo apt install python3.11 python3.11-dev  # Ubuntu/Debian
# or
sudo dnf install python3.11 python3.11-devel  # Fedora
```

Verify: `python --version` (should show 3.11.X)

Sources: [Python Downloads][web:162], [Installation Guide][web:179]

#### 4. **C++ Compiler**

**Windows - MSYS2 with MinGW-w64** (REQUIRED):

1. **Download and install MSYS2**: https://www.msys2.org/
   - Install to default location: `C:\msys64`

2. **Open MSYS2 terminal** and run:
   ```
   # Update package database
   pacman -Syu
   
   # Close and reopen MSYS2 terminal, then:
   pacman -S --needed base-devel mingw-w64-x86_64-toolchain mingw-w64-x86_64-binutils
   ```
   Press Enter to install all packages when prompted.

3. **Add to System PATH** (CRITICAL):
   - Open "Environment Variables" in Windows Settings
   - Find "Path" under "System variables"
   - Click "Edit" → "New"
   - Add: `C:\msys64\mingw64\bin`
   - Click OK on all dialogs

   **Or temporarily in PowerShell**:
   ```
   $env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
   ```

4. **Verify installation** (restart PowerShell first):
   ```
   gcc --version
   dlltool --version  # Should show GNU dlltool
   ```

**macOS**:
```
xcode-select --install
```

**Linux**:
```
sudo apt install build-essential  # Ubuntu/Debian
# or
sudo dnf install gcc-c++ make     # Fedora
```

Sources: [MSYS2][web:148], [MSYS2 Installation Guide][web:83]

## Installation & Building

### Clone the Repository

```
git clone https://github.com/yourusername/project_frank.git
cd project_frank
```

### Build Everything (All Platforms)

**Windows**:
```
.\scripts\build_all.ps1
```

**macOS/Linux**:
```
chmod +x scripts/build_all.sh
./scripts/build_all.sh
```

This script:
1. Compiles the Go library (`frankgo.a`/`frankgo.lib`)
2. Compiles the C++ library (`frankcpp.a`/`frankcpp.lib`)
3. Builds the Rust binary with all dependencies

### Building Individual Components

#### Rust Only
```
cd rust
cargo build --release
```

#### Go Library
```
cd go
# Windows (GNU toolchain)
go build -buildmode=c-archive -o libfrankgo.a frankgo.go

# Linux/macOS
go build -buildmode=c-archive -o libfrankgo.a frankgo.go
```

#### C++ Library
```
cd cpp
# Build handled by Rust build.rs automatically
```

## Running

```
cd rust
cargo run --release

# Or after building:
./target/release/project-frank  # Linux/macOS
.\target\release\project-frank.exe  # Windows
```

## Project Structure

```
project_frank/
├── rust/           # Main Rust application
│   ├── src/
│   │   ├── main.rs       # Entry point & TUI
│   │   ├── lib.rs        # Library exports
│   │   ├── ffi.rs        # FFI bridges (Go/C++)
│   │   ├── db.rs         # SQLite caching
│   │   └── ai.rs         # Python AI integration (PyO3)
│   └── build.rs          # Build script for Go/C++ compilation
├── go/             # Go domain services
│   └── frankgo.go        # Music/Sports API handlers (WIP)
├── cpp/            # C++ performance modules
│   ├── frankcpp.cpp      # Fast operations (WIP)
│   └── frankcpp.h
├── python/         # Python AI models (future)
│   └── models.py         # LLM integration (placeholder)
└── scripts/        # Build automation
    ├── build_all.ps1     # Windows build script
    └── build_all.sh      # Unix build script
```

## Troubleshooting

### Windows: `dlltool.exe` Not Found

**Error**: `error calling dlltool 'dlltool.exe': program not found`

**Fix**:
1. Install complete MSYS2 toolchain:
   ```
   pacman -S --needed mingw-w64-x86_64-binutils
   ```
2. Verify `dlltool` is in PATH:
   ```
   where.exe dlltool
   # Should show: C:\msys64\mingw64\bin\dlltool.exe
   ```
3. Add `C:\msys64\mingw64\bin` to PATH if missing

### Windows: Library Not Found Errors

**Error**: `could not find native static library 'frankgo'`

**Fix**:
1. Ensure you're using GNU toolchain (not MSVC):
   ```
   rustc --version --verbose
   # Must show: host: x86_64-pc-windows-gnu
   ```
2. Clean and rebuild:
   ```
   Remove-Item -Recurse -Force .\rust\target\
   .\scripts\build_all.ps1
   ```

### MinGW/MSVC Mixing Errors

**Error**: `unresolved external symbol __mingw_fprintf`

**Cause**: Mixing MinGW (Go) with MSVC (Rust)

**Fix**: Switch Rust to GNU toolchain:
```
rustup default stable-x86_64-pc-windows-gnu
```

### Python Module Not Found

**Error**: `No module named 'XXX'`

**Fix**:
```
pip install -r requirements.txt  # (when added)
```

## Development

### Running Tests

```
cd rust
cargo test
```

### Code Style

```
# Rust
cargo fmt
cargo clippy

# Go
cd go
go fmt ./...

# C++
# Use clang-format (config TBD)
```

## Roadmap

- [ ] Complete MusicBrainz API integration (Go)
- [ ] Complete Sports API integration (Go)
- [ ] Implement actual AI model integration (Python/PyO3)
- [ ] Add multi-model support and selection CLI
- [ ] Configuration file support (TOML/YAML)
- [ ] Enhanced TUI with menus and tabs
- [ ] Add tests for all modules
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Documentation improvements
- [ ] Performance benchmarks

## Contributing

This is a personal learning project. Contributions, suggestions, and feedback are welcome!

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built with:
- [Rust](https://www.rust-lang.org/)
- [PyO3](https://pyo3.rs/) - Python FFI
- [Ratatui](https://ratatui.rs/) - Terminal UI
- [rusqlite](https://github.com/rusqlite/rusqlite) - SQLite wrapper
- [Go](https://go.dev/)
- [MSYS2](https://www.msys2.org/) - Windows GNU toolchain

---

**Note**: This project is experimental and under active development. Expect breaking changes and incomplete features.
```

## License

**GNU Affero General Public License v3.0 (AGPL-3.0)**

This project is licensed under the AGPL-3.0 license. This means:

- ✅ **Free to use, modify, and distribute**
- ✅ **Attribution required** - You must credit randomSPPOCguy and link to this repository
- ✅ **Share-alike** - Modified versions must also be open-source under AGPL-3.0
- ✅ **Network use clause** - If you use this code in a web service, you must share your source code

### Attribution Requirements

If you use this code or substantial portions of it:
1. Credit the original author: **randomSPPOCguy** (https://github.com/randomSPPOCguy)
2. Link to this repository: https://github.com/randomSPPOCguy/project_frank
3. Specify which parts of this code you used
4. Share your modifications under the same AGPL-3.0 license

See [LICENSE](LICENSE) for full details.

**Why AGPL?** The AGPL ensures that any improvements or modifications to this code
benefit the entire community. Unlike GPL, AGPL requires sharing source code even when
the software is used as a web service.
