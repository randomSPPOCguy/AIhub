#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export FRANK_PYTHON_PATH="${ROOT_DIR}/python"
export FRANK_CACHE_PATH="${ROOT_DIR}/cache.sqlite3"

pushd "${ROOT_DIR}/rust" >/dev/null
echo "Running Rust tests..."
cargo test --lib
echo "Tests completed successfully!"
popd >/dev/null
