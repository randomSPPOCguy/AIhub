# Start AI Hub Server
# Run this from PowerShell

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Starting AI Hub Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to the AI Hub directory (project root = parent of this script folder)
$aiHubPath = Split-Path -Parent $PSScriptRoot
Set-Location $aiHubPath

$configPath = Join-Path $aiHubPath "config.env"
$port = 7071
$baseUrl = "http://localhost:$port"
$wsUrl = "ws://localhost:$port/ws/room"
if (Test-Path $configPath) {
    $envMap = @{}
    foreach ($line in Get-Content $configPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $pair = $trimmed.Split("=", 2)
        if ($pair.Length -ne 2) { continue }
        $envMap[$pair[0].Trim()] = $pair[1].Trim().Trim('"')
    }
    if ($envMap.ContainsKey("PORT")) {
        $candidate = 0
        if ([int]::TryParse($envMap["PORT"], [ref]$candidate)) {
            $port = $candidate
        }
    }
    if ($envMap["AIHUB_BASE_URL"]) {
        $baseUrl = $envMap["AIHUB_BASE_URL"]
    } elseif ($envMap["PUBLIC_BASE_URL"]) {
        $baseUrl = $envMap["PUBLIC_BASE_URL"]
    } else {
        $baseUrl = "http://localhost:$port"
    }
    $wsBase = $null
    if ($envMap["AIHUB_WS_BASE_URL"]) {
        $wsBase = $envMap["AIHUB_WS_BASE_URL"]
    } else {
        $wsBase = if ($baseUrl.StartsWith("https://")) {
            $baseUrl.Replace("https://", "wss://")
        } else {
            $baseUrl.Replace("http://", "ws://")
        }
    }
    $wsUrl = "$wsBase/ws/room"
}

Write-Host "Location: $aiHubPath" -ForegroundColor Green
Write-Host "Starting server on $baseUrl" -ForegroundColor Green
Write-Host "WebSocket available at $wsUrl" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
npm start
