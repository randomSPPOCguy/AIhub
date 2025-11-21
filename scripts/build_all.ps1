Param(
    [string]$Configuration = "release"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$Env:FRANK_PYTHON_PATH = Join-Path $Root "python"
$Env:FRANK_CACHE_PATH = Join-Path $Root "cache.sqlite3"

Push-Location (Join-Path $Root "rust")
cargo build --$Configuration
Pop-Location

Write-Host "Artifacts ready under rust\target\$Configuration"
