# Kill all AIhub-related processes
# Use this if you have orphaned processes from previous runs

Write-Host "Killing all AIhub-related processes..." -ForegroundColor Yellow
Write-Host ""

# Kill all Node.js processes
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    Write-Host "Found $($nodeProcesses.Count) Node.js process(es):" -ForegroundColor Yellow
    foreach ($proc in $nodeProcesses) {
        Write-Host "  - PID $($proc.Id) ($($proc.Path))" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Killed all Node.js processes" -ForegroundColor Green
} else {
    Write-Host "No Node.js processes found" -ForegroundColor Gray
}

Write-Host ""

# Kill Python processes related to our services
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -match "(server\.py|uvicorn|app:app|python_ai|python_enrichment)" -or $_.Path -match "(python_ai|python_enrichment)"
    } catch {
        $false
    }
}

if ($pythonProcesses) {
    Write-Host "Found $($pythonProcesses.Count) Python process(es) (server/uvicorn):" -ForegroundColor Yellow
    foreach ($proc in $pythonProcesses) {
        Write-Host "  - PID $($proc.Id)" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Killed Python server processes" -ForegroundColor Green
} else {
    Write-Host "No Python server processes found" -ForegroundColor Gray
}

Write-Host ""

# Kill processes on our ports (catch anything else)
$portsToCheck = @(7071, 8000, 8001)
foreach ($port in $portsToCheck) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Found process on port $port: $($proc.Name) (PID: $pid)" -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host ""
Write-Host "All AIhub services killed!" -ForegroundColor Green
Write-Host "You can now run .\start.ps1 to start fresh" -ForegroundColor Cyan
