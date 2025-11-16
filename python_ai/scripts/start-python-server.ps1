# Start Python ONNX GenAI Server
# Run this from PowerShell

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Starting Python ONNX GenAI Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$projectRoot = Split-Path -Parent $scriptDir
$configPath = Join-Path $projectRoot "config.env"
if (-not (Test-Path $configPath)) {
    $projectRoot = Split-Path -Parent $projectRoot
    $configPath = Join-Path $projectRoot "config.env"
}

$pythonHost = "0.0.0.0"
$pythonPort = 8000
$pythonBase = "http://localhost:$pythonPort"
if (Test-Path $configPath) {
    $envMap = @{}
    foreach ($line in Get-Content $configPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $pair = $trimmed.Split("=", 2)
        if ($pair.Length -ne 2) { continue }
        $envMap[$pair[0].Trim()] = $pair[1].Trim().Trim('"')
    }
    if ($envMap["PYTHON_AI_HOST"]) { $pythonHost = $envMap["PYTHON_AI_HOST"] }
    if ($envMap.ContainsKey("PYTHON_AI_PORT")) {
        $candidate = 0
        if ([int]::TryParse($envMap["PYTHON_AI_PORT"], [ref]$candidate)) {
            $pythonPort = $candidate
        }
    }
    if ($envMap["PYTHON_AI_BASE"]) {
        $pythonBase = $envMap["PYTHON_AI_BASE"]
    } else {
        $pythonBase = "http://localhost:$pythonPort"
    }
}
$pythonBase = $pythonBase.TrimEnd("/")

# Activate virtual environment
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "ERROR: Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "Location: $scriptDir" -ForegroundColor Green
Write-Host "Starting Python server on $pythonBase (host $pythonHost)" -ForegroundColor Green
Write-Host "API endpoints:" -ForegroundColor Green
Write-Host "  - Health: $pythonBase/api/health" -ForegroundColor Gray
Write-Host "  - Chat: $pythonBase/api/chat" -ForegroundColor Gray
Write-Host "  - Models: $pythonBase/api/models" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
python server.py

