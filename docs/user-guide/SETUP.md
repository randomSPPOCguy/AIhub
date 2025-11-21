# Project Frank - Setup Guide

## Prerequisites

To build and run Project Frank, you need:

### 1. Rust
- Install from: https://rustup.rs/
- Run: `rustup install stable`
- Verify: `rustc --version` and `cargo --version`

### 2. Go
- Install from: https://go.dev/dl/
- Version: 1.21 or later
- Verify: `go version`
- Make sure CGO is enabled (default on most installations)

### 3. C++ Compiler
**Windows:**
- Install Visual Studio Build Tools or Visual Studio Community
- Or install MSYS2/MinGW-w64
- Verify: `g++ --version` or `cl` (Visual Studio)

**Linux:**
- `sudo apt-get install build-essential g++`

**macOS:**
- `xcode-select --install`

### 4. Python 3.11
- Already installed ✓ (version 3.11.9)
- For PyO3, you may need Python development headers:
  - **Windows**: Usually included with Python installer
  - **Linux**: `sudo apt-get install python3.11-dev`
  - **macOS**: Usually included with Python

### 5. SQLite
- Usually comes with the OS or Python
- Rust's `rusqlite` crate handles this automatically

## Build Process

1. **Build everything:**
   ```powershell
   .\scripts\build_all.ps1
   ```
   Or on Linux/Mac:
   ```bash
   ./scripts/build_all.sh
   ```

2. **Run tests:**
   ```powershell
   .\scripts\run_all.ps1
   ```

3. **Run the application:**
   ```powershell
   cd rust
   cargo run --release
   ```

## Current Status

- ✅ Python code validated
- ⏳ Rust, Go, and C++ need to be installed to build

## Troubleshooting

### Build fails with "go: command not found"
- Install Go and add it to your PATH
- Restart your terminal after installation

### Build fails with C++ compiler errors
- On Windows: Install Visual Studio Build Tools
- Make sure the compiler is in your PATH

### PyO3 build errors
- Ensure Python 3.11 is installed and in PATH
- On Linux, install `python3.11-dev` package

### Shared library linking errors
- On Windows, DLLs should be in the same directory as the executable
- The build script handles this automatically

