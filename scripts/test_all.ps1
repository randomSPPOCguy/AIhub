# test_all.ps1 - Development testing
# For production use, run run_all.ps1 instead

$ROOT_DIR = Split-Path -Parent $PSScriptRoot

$env:FRANK_PYTHON_PATH = Join-Path $ROOT_DIR "python"
$env:FRANK_CACHE_PATH = Join-Path $ROOT_DIR "cache.sqlite3"

Push-Location (Join-Path $ROOT_DIR "rust")

Write-Host "Running Project Frank tests..." -ForegroundColor Yellow

# Run all tests
cargo test

if ($LASTEXITCODE -eq 0) {
    Write-Host "Tests completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Tests failed!" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}

Pop-Location
