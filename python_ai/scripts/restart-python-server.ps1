# Restart Python ONNX GenAI Server
# Run this from PowerShell

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Restarting Python ONNX GenAI Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Stop existing server
Write-Host "Stopping existing server..." -ForegroundColor Yellow
& "$scriptDir\stop-python-server.ps1"

Write-Host ""
Start-Sleep -Seconds 2

# Start new server
Write-Host "Starting new server..." -ForegroundColor Yellow
& "$scriptDir\start-python-server.ps1"

