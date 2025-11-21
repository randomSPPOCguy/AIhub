# Developer Guide

## Prerequisites

- Rust stable toolchain
- Go 1.21+
- Python 3.11 with headers/libraries for PyO3
- C++17 compiler (clang++/g++)
- SQLite development libs (`libsqlite3-dev` on Debian-based systems)

## Environment Variables

- `FRANK_PYTHON_PATH`: path to the `python/` directory (default inferred).
- `FRANK_CACHE_PATH`: desired SQLite cache path (defaults to `cache.sqlite3` in repo root).

## Build

```bash
./scripts/build_all.sh          # Linux/macOS
pwsh scripts/build_all.ps1      # Windows
```

## Run

```bash
./scripts/run_all.sh
```

This runs `cargo test` followed by the interactive TUI (`cargo run`).

## Testing Notes

- Rust unit/integration tests: `cargo test` from `rust/`.
- Python pipeline: run `python -m pytest` under `python/` when real clients are implemented.
- Go/C++ smoke tests: add `go test` and `ctest` invocations once logic is fleshed out.

## Extending the Pipeline

1. Replace placeholders inside `go/frankgo.go` and `cpp/frankcpp.cpp` with real logic.
2. Flesh out `python/enrichment_pipeline.py` to perform authenticated requests and richer parsing.
3. Plug a real LLM through `python/ai_gateway.py` using your preferred backend.
4. Evolve the Rust orchestrator to support streaming responses by enabling the `streaming` feature.
