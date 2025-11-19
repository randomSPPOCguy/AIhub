# start.ps1 - AIhub Unified Console
# Auto-starts all services and launches interactive console

$ErrorActionPreference = "Continue"
$global:pythonJob = $null
$global:enrichmentJob = $null

Clear-Host
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  AIhub 1.4.1 - Starting All Services" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Start Python AI Server silently
Write-Host "[1/3] Starting Python ONNX AI Server (port 8000)..." -ForegroundColor Gray
$pythonAiPath = Join-Path $PSScriptRoot "python_ai"
$global:pythonJob = Start-Job -ScriptBlock {
    param($Path)
    Set-Location $Path
    if (Test-Path ".\.venv\Scripts\Activate.ps1") {
        .\.venv\Scripts\Activate.ps1
    }
    python server.py 2>&1
} -ArgumentList $pythonAiPath
Start-Sleep -Seconds 3

# Start Enrichment Service silently
Write-Host "[2/3] Starting Python Enrichment Service (port 8001)..." -ForegroundColor Gray
$enrichPath = Join-Path $PSScriptRoot "python_enrichment"
$global:enrichmentJob = Start-Job -ScriptBlock {
    param($Path)
    Set-Location $Path
    python -m uvicorn app:app --host 0.0.0.0 --port 8001 2>&1
} -ArgumentList $enrichPath
Start-Sleep -Seconds 3

# Check and kill any process using port 7071 (Node.js server port)
Write-Host "[3/3] Starting Node.js AIhub Server (port 7071)..." -ForegroundColor Gray
$port7071Connections = Get-NetTCPConnection -LocalPort 7071 -ErrorAction SilentlyContinue
if ($port7071Connections) {
    $pids = $port7071Connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc -and $proc.Name -eq "node") {
            Write-Host "  Killing existing Node.js process on port 7071 (PID: $pid)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    }
}
Start-Sleep -Seconds 2
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  Services started! Launching AIhub Console..." -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Start-Sleep -Seconds 1

# Set environment variable for enhanced mode
$env:AIHUB_UNIFIED_MODE = "true"
$env:AIHUB_AUTO_START = "true"

# Cleanup function
$cleanupScript = {
    Write-Host ""
    Write-Host "Shutting down all services..." -ForegroundColor Yellow

    if ($global:pythonJob) {
        Stop-Job -Job $global:pythonJob -ErrorAction SilentlyContinue
        Remove-Job -Job $global:pythonJob -Force -ErrorAction SilentlyContinue
    }

    if ($global:enrichmentJob) {
        Stop-Job -Job $global:enrichmentJob -ErrorAction SilentlyContinue
        Remove-Job -Job $global:enrichmentJob -Force -ErrorAction SilentlyContinue
    }

    # Kill all Node.js processes
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Kill processes on our ports
    Get-NetTCPConnection -LocalPort 7071,8000,8001 -ErrorAction SilentlyContinue | ForEach-Object {
        $processId = $_.OwningProcess
        if ($processId -gt 0) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Kill Python server processes
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -match "(server\.py|uvicorn|app:app)"
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host "All services stopped. Goodbye!" -ForegroundColor Green
}

# Register cleanup on exit
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupScript | Out-Null

try {
    # Start Node.js server (foreground)
    npm start
} finally {
    # Cleanup
    & $cleanupScript
}
