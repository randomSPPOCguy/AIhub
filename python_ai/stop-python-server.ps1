# Stop Python ONNX GenAI Server
# Run this from PowerShell

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Stopping Python ONNX GenAI Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Find Python processes running server.py
$processes = @()
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    $isServer = $false
    
    # Check if path contains python_ai
    if ($proc.Path -like "*python_ai*") {
        $isServer = $true
    } else {
        # Try to get command line
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmdLine -like "*server.py*") {
                $isServer = $true
            }
        } catch {
            # If we can't get command line, skip
        }
    }
    
    if ($isServer) {
        $processes += $proc
    }
}

if ($processes) {
    Write-Host "Found $($processes.Count) Python server process(es):" -ForegroundColor Yellow
    foreach ($proc in $processes) {
        Write-Host "  - PID: $($proc.Id) | Name: $($proc.Name) | Path: $($proc.Path)" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "Stopping processes..." -ForegroundColor Yellow
    
    $processes | Stop-Process -Force
    
    Start-Sleep -Seconds 1
    
    # Verify they're stopped
    $remaining = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $processes.Id -contains $_.Id
    }
    
    if ($remaining) {
        Write-Host "WARNING: Some processes may still be running" -ForegroundColor Red
    } else {
        Write-Host "Successfully stopped all Python server processes" -ForegroundColor Green
    }
} else {
    Write-Host "No Python server processes found running" -ForegroundColor Gray
}

# Also check if the port is in use and offer to kill by port
Write-Host ""
Write-Host "Checking port 8000..." -ForegroundColor Cyan
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

if ($portInUse) {
    Write-Host "Port 8000 is still in use by PID: $($portInUse.OwningProcess)" -ForegroundColor Yellow
    $killByPort = Read-Host "Kill process on port 8000? (y/n)"
    if ($killByPort -eq 'y' -or $killByPort -eq 'Y') {
        Stop-Process -Id $portInUse.OwningProcess -Force
        Write-Host "Killed process on port 8000" -ForegroundColor Green
    }
} else {
    Write-Host "Port 8000 is free" -ForegroundColor Green
}

Write-Host ""

