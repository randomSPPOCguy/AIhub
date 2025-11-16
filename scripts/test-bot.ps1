# Test bot response with word "bot" only
# Run from any folder: .\test-bot.ps1
# Or paste this command directly in PowerShell

$apiKey = "YOUR_API_KEY_HERE"  # Replace with your API key, or set AIHUB_REQUIRE_KEY=false in config.env
$body = @{
    messages = @(
        @{
            role = "user"
            content = "bot"
        }
    )
} | ConvertTo-Json

$headers = @{
    "Content-Type" = "application/json"
    "X-AIHub-Key" = $apiKey
}

try {
    $response = Invoke-RestMethod -Uri "http://localhost:7071/hub/chat" -Method POST -Headers $headers -Body $body
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "`nAPI key required. Either:" -ForegroundColor Yellow
        Write-Host "1. Generate one: npm run keygen -- --label 'test'" -ForegroundColor Cyan
        Write-Host "2. Or disable in config.env: AIHUB_REQUIRE_KEY=false" -ForegroundColor Cyan
    }
}

