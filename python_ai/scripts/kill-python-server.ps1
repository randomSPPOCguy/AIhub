# Force kill Python ONNX GenAI Server (more aggressive)
# Run this from PowerShell

Write-Host "==================================" -ForegroundColor Red
Write-Host "  Force Killing Python ONNX GenAI Server" -ForegroundColor Red
Write-Host "==================================" -ForegroundColor Red
Write-Host ""

# Kill all Python processes that might be the server
Write-Host "Searching for Python processes..." -ForegroundColor Yellow

$pythonProcs = Get-Process python -ErrorAction SilentlyContinue

if ($pythonProcs) {
    Write-Host "Found $($pythonProcs.Count) Python process(es):" -ForegroundColor Yellow
    foreach ($proc in $pythonProcs) {
        $cmdLine = ""
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
        } catch {}
        
        $isServer = $cmdLine -like "*server.py*" -or $proc.Path -like "*python_ai*"
        $marker = if ($isServer) { " [SERVER]" } else { "" }
        Write-Host "  - PID: $($proc.Id) | Path: $($proc.Path)$marker" -ForegroundColor Gray
    }
    
    Write-Host ""
    $confirm = Read-Host "Kill ALL Python processes? (y/n)"
    
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        $pythonProcs | Stop-Process -Force
        Write-Host "Killed all Python processes" -ForegroundColor Green
    } else {
        Write-Host "Cancelled" -ForegroundColor Gray
    }
} else {
    Write-Host "No Python processes found" -ForegroundColor Gray
}

# Force kill anything on port 8000
Write-Host ""
Write-Host "Checking port 8000..." -ForegroundColor Cyan
$portConn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

if ($portConn) {
    foreach ($conn in $portConn) {
        Write-Host "Force killing PID $($conn.OwningProcess) on port 8000..." -ForegroundColor Yellow
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Port 8000 cleared" -ForegroundColor Green
} else {
    Write-Host "Port 8000 is free" -ForegroundColor Green
}

Write-Host ""

