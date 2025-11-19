# Kill process using a specific port
# Usage: .\scripts\kill-port.ps1 -Port 7071

param(
    [Parameter(Mandatory=$true)]
    [int]$Port
)

Write-Host "Checking for processes using port $Port..." -ForegroundColor Yellow

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "No process found using port $Port" -ForegroundColor Green
    exit 0
}

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($pid in $processIds) {
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "Found process: $($process.Name) (PID: $pid)" -ForegroundColor Yellow
        Write-Host "Killing process $pid..." -ForegroundColor Red
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Host "Process $pid killed" -ForegroundColor Green
    }
}

Write-Host "Port $Port is now free" -ForegroundColor Green
