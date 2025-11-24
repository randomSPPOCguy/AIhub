#!/usr/bin/env bash
# run_all.sh - Production startup (no tests)
# For testing, use test_all.sh instead

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export FRANK_PYTHON_PATH="${ROOT_DIR}/python"
export FRANK_CACHE_PATH="${ROOT_DIR}/cache.sqlite3"

pushd "${ROOT_DIR}/rust" >/dev/null

echo "Building Project Frank..."

# Build first to ensure all compilation completes before running
cargo build --release

if [ $? -eq 0 ]; then
    echo "Starting Project Frank..."

    # Run the pre-built binary
    ./target/release/project-frank
else
    echo "Build failed!"
    popd >/dev/null
    exit 1
fi

popd >/dev/null

