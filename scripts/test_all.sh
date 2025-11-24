#!/usr/bin/env bash
# test_all.sh - Development testing
# For production use, run run_all.sh instead

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export FRANK_PYTHON_PATH="${ROOT_DIR}/python"
export FRANK_CACHE_PATH="${ROOT_DIR}/cache.sqlite3"

pushd "${ROOT_DIR}/rust" >/dev/null

echo "Running Project Frank tests..."

# Run all tests
cargo test

if [ $? -eq 0 ]; then
    echo "Tests completed successfully!"
else
    echo "Tests failed!"
    popd >/dev/null
    exit 1
fi

popd >/dev/null
