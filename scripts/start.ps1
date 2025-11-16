# start.ps1 - Start AI Hub server

Write-Host "Starting AI Hub 1.1..." -ForegroundColor Green

# Set port (default to 8001 if not set)
if (-not $env:PORT) {
    $env:PORT = '8001'
    Write-Host "Using default port: $env:PORT" -ForegroundColor Cyan
}

# Start the server
npm start
