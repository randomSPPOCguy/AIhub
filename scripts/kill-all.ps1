# Quick kill script - kills all AIhub processes
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -match "(server\.py|uvicorn|app:app)"
    } catch { $false }
} | Stop-Process -Force
Get-NetTCPConnection -LocalPort 7071,8000,8001 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "All AIhub processes killed!" -ForegroundColor Green
