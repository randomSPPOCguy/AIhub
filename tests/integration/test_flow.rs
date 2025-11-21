//! Integration test harness placeholder. Real end-to-end tests live alongside
//! the Rust crate (see `rust/tests/`), but this file captures the intended flow:
//!
//! 1. Launch the Rust binary with `cargo run`.
//! 2. Send a query such as "Tell me about Taylor Swift".
//! 3. Verify that:
//!    - Go music subsystem emits a JSON block with `signal: "enrich"`.
//!    - Python enrichment returns MusicBrainz -> Wikidata -> Wikipedia data.
//!    - The final TUI response mentions the enrichment sources.
//!
//! Future work: convert this description into an automated smoke test that can
//! be executed within CI (likely via an expect-style script or a Rust integration
//! test that spawns the binary and feeds stdin/stdout).
