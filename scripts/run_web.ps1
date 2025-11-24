# Run Project Frank in Web Mode with environment variables loaded

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path $scriptRoot -Parent
$configPath = Join-Path $projectRoot "config.env"

Write-Host "Loading configuration from config.env..." -ForegroundColor Cyan

# Load environment variables from config.env
if (Test-Path $configPath) {
    Get-Content $configPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($value) {
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
                Write-Host "  Set $name" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "Warning: config.env not found. API keys will not be loaded." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting Project Frank Web UI..." -ForegroundColor Cyan
Write-Host ""

# Run the web server
$rustDir = Join-Path $projectRoot "rust"
Push-Location $rustDir
try {
    $existing = Get-Process -Name "project-frank" -ErrorAction SilentlyContinue
    if ($existing) {
        $pids = ($existing | Select-Object -ExpandProperty Id) -join ", "
        Write-Host "Stopping existing project-frank.exe (PID: $pids)..." -ForegroundColor Yellow
        $existing | Stop-Process -Force
        Start-Sleep -Seconds 1
    }

    cargo run --release -- --mode web
} finally {
    Pop-Location
}
