# PROJECT FRANK - Unified Polyglot Foundation

This document captures the architectural intent, requirements, and phased plan
for the unified polyglot bot runtime. It is meant to guide implementation
efforts and document the contract between Rust, Python, Go, and C++ modules.

## Objectives

- Deliver a single-process monolith with Rust as the orchestrator and shared
  cache owner.
- Embed Python via PyO3 for NLG, enrichment orchestration, and LLM access.
- Load Go and C++ shared libraries via FFI for music/sports and
  game/Discord features respectively.
- Share a central SQLite cache with TTL-aware APIs accessible through Rust.
- Provide an enrichment pipeline that chains MusicBrainz -> Wikidata ->
  Wikipedia and feeds the LLM response system.

## System Overview

1. **Rust Core**
   - Handles input routing, ratatui-based TUI, cache coordination, and FFI.
   - Exposes safe wrappers that convert JSON payloads to native structs.
2. **Python Layer**
   - Implements `enrich_entity` and `generate_response`.
   - Manages enrichment API chaining and prompt construction.
3. **Go Layer**
   - Provides `go_music_query` and `go_sports_query` functions compiled as
     `libfrankgo`.
4. **C++ Layer**
   - Provides `cpp_game_query` and `cpp_discord_status` functions compiled as
     `libfrankcpp`.
5. **SQLite Cache**
   - Stores enrichment results, responses, and TTL metadata.
   - Schema defined in `sql/schema.sql`.

## Build & Toolchain Requirements

- Rust stable (latest) + Cargo.
- Go 1.21+ (CGO enabled).
- C++17 compiler (clang++/g++) with shared library support.
- Python 3.11 headers/libraries compatible with PyO3.
- SQLite development libraries.

## Build Flow

1. `cargo build` executes `rust/build.rs`.
2. `build.rs` compiles:
   - Go sources via `go build -buildmode=c-shared -o target/libfrankgo.(so|dll|dylib)`.
   - C++ sources via the `cc` crate invoking the configured compiler.
3. Rust links against the generated artifacts and embeds Python.

## Testing Strategy

- Rust unit tests cover cache logic, intent detection, and wrappers.
- Integration tests live under `tests/integration/` and call the Rust binary
  (or modules) with mocked data.
- Python modules contain doctests for API chain steps.
- Shared libraries expose smoke-test entry points invoked from Rust `#[cfg(test)]`
  modules.

## Deployment Considerations

- Use environment variables (`FRANK_PYTHON_PATH`, `FRANK_CACHE_PATH`, etc.) to
  configure runtime paths.
- Provide optional Unix socket streaming by enabling the feature flag
  `streaming` in Cargo.
- Ship pre-built shared libraries alongside the Rust binary for production.

## Next Steps

1. Implement enrichment API clients with proper rate limiting.
2. Integrate a real LLM backend (local or hosted).
3. Expand the Go and C++ modules beyond stub logic.
4. Harden the cache layer with connection pooling.
5. Automate CI/CD to compile and run tests on every push.
