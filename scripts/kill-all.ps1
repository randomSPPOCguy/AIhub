# Kill all AIhub processes and show what was terminated

Write-Host "Killing AIhub processes..." -ForegroundColor Yellow
Write-Host ""

# Kill Node.js processes
$nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcs) {
    Write-Host "Found $($nodeProcs.Count) Node.js process(es):" -ForegroundColor Cyan
    foreach ($proc in $nodeProcs) {
        Write-Host "  - PID $($proc.Id)" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✓ Killed all Node.js processes" -ForegroundColor Green
} else {
    Write-Host "No Node.js processes found" -ForegroundColor Gray
}

Write-Host ""

# Kill Python server processes
$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -match "(server\.py|uvicorn|app:app)" -or $_.Path -match "(python_ai|python_enrichment)"
    } catch { $false }
}

if ($pythonProcs) {
    Write-Host "Found $($pythonProcs.Count) Python server process(es):" -ForegroundColor Cyan
    foreach ($proc in $pythonProcs) {
        Write-Host "  - PID $($proc.Id)" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✓ Killed all Python server processes" -ForegroundColor Green
} else {
    Write-Host "No Python server processes found" -ForegroundColor Gray
}

Write-Host ""

# Kill processes on ports
$ports = @(7071, 8000, 8001)
$totalKilled = 0
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Found process on port $port: $($proc.Name) (PID: $pid)" -ForegroundColor Cyan
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                $totalKilled++
                Write-Host "  ✓ Killed" -ForegroundColor Green
            }
        }
    }
}

if ($totalKilled -eq 0) {
    Write-Host "No processes found on ports 7071, 8000, 8001" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "All AIhub processes terminated!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
