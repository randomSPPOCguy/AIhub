# PROJECT FRANK

Unified polyglot bot foundation driven by a Rust orchestrator with embedded
Python, Go, and C++ modules. This repository provides the scaffolding,
documentation, and sample stubs required to start implementing the production
system described in the RFC.

## Repository Layout

```
project_frank/
|-- README.md
|-- docs/
|   `-- rfc.md
|-- rust/
|   |-- Cargo.toml
|   |-- build.rs
|   `-- src/
|       |-- api_chain.rs
|       |-- cache.rs
|       |-- ffi.rs
|       |-- intent.rs
|       |-- main.rs
|       |-- nlg_processor.rs
|       `-- tui.rs
|-- go/
|   `-- frankgo.go
|-- cpp/
|   `-- frankcpp.cpp
|-- python/
|   |-- ai_gateway.py
|   `-- enrichment_pipeline.py
|-- sql/
|   `-- schema.sql
|-- scripts/
|   |-- build_all.ps1
|   |-- build_all.sh
|   |-- run_all.ps1
|   `-- run_all.sh
|-- tests/
|   |-- integration/
|   |   `-- test_flow.rs
|   `-- unit/
|       `-- cache_tests.rs
|-- sample_data/
|   `-- session_example.json
`-- .github/
    `-- workflows/
        `-- ci.yml
```

## Quick Start

1. Install the prerequisites referenced in `docs/rfc.md`.
2. Run `scripts/build_all.sh` (or `.ps1` on Windows) to compile Go/C++ shared
   libraries and build the Rust binary.
3. Execute `scripts/run_all.sh` to launch the TUI and run smoke tests.

## Status

This is a bootstrap foundation. Many functions intentionally return placeholder
data so developers can plug in the real API calls and LLM connections while
keeping the cross-language wiring stable and testable.
