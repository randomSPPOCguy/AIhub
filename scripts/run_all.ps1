$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$Env:FRANK_PYTHON_PATH = Join-Path $Root "python"
$Env:FRANK_CACHE_PATH = Join-Path $Root "cache.sqlite3"

Push-Location (Join-Path $Root "rust")
cargo test
cargo run --bin project-frank
Pop-Location
