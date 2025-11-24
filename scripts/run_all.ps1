# run_all.ps1 - Production startup (no tests)
# For testing, use test_all.ps1 instead

$ROOT_DIR = Split-Path -Parent $PSScriptRoot

$env:FRANK_PYTHON_PATH = Join-Path $ROOT_DIR "python"
$env:FRANK_CACHE_PATH = Join-Path $ROOT_DIR "cache.sqlite3"

Push-Location (Join-Path $ROOT_DIR "rust")

Write-Host "Building Project Frank..." -ForegroundColor Cyan

# Build first to ensure all compilation completes before running
cargo build --release

if ($LASTEXITCODE -eq 0) {
    Write-Host "Starting Project Frank..." -ForegroundColor Green

    # Run the pre-built binary
    .\target\release\project-frank.exe
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}

Pop-Location

