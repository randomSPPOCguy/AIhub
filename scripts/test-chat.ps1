# test-chat.ps1 - Quick test script for AIhub chat API
# Usage: .\test-chat.ps1 -ApiKey "aih_xxxxxxxxxxxxx"

param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey,
    
    [string]$Url = "http://localhost:7071/hub/chat",
    [switch]$Debug,
    [switch]$Simple
)

$headers = @{
    "Content-Type" = "application/json"
    "X-AIHub-Key" = $ApiKey
}

if ($Simple) {
    # Simple test without metadata
    $body = @{
        messages = @(
            @{
                role = "user"
                content = "Hello! Can you hear me?"
            }
        )
    } | ConvertTo-Json -Depth 5
} else {
    # Full test with metadata
    $body = @{
        messages = @(
            @{
                role = "user"
                content = "What song is currently playing?"
            }
        )
        metadata = @{
            room_id = "test-room-123"
            room_source = "hangfm"
            user_id = "test-user-456"
            username = "testuser"
            now_playing = @{
                artist = "Deftones"
                title = "Change"
                album = "White Pony"
                year = 2000
            }
            stage = @("dj1", "dj2")
            dancefloor = @("u1", "u2")
            last_event = "user_joined"
        }
        temperature = 0.7
        maxTokens = 512
    } | ConvertTo-Json -Depth 10
}

$requestUrl = $Url
if ($Debug) {
    $requestUrl = "$Url?debug=1"
}

Write-Host "Testing AIhub chat API..." -ForegroundColor Cyan
Write-Host "URL: $requestUrl" -ForegroundColor Gray
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $requestUrl -Method POST -Headers $headers -Body $body
    
    Write-Host "✅ SUCCESS!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Yellow
    $response | ConvertTo-Json -Depth 10
    
    if ($Debug -and $response.debug) {
        Write-Host ""
        Write-Host "=== DEBUG INFO ===" -ForegroundColor Magenta
        Write-Host "System Prompt:" -ForegroundColor Yellow
        Write-Host $response.debug.systemPrompt -ForegroundColor Gray
        Write-Host ""
        Write-Host "Metadata:" -ForegroundColor Yellow
        $response.debug.metadata | ConvertTo-Json -Depth 5
    }
    
} catch {
    Write-Host "❌ ERROR!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "Status Code: $statusCode" -ForegroundColor Red
        
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $reader.BaseStream.Position = 0
            $reader.DiscardBufferedData()
            $responseBody = $reader.ReadToEnd()
            Write-Host "Response Body:" -ForegroundColor Yellow
            Write-Host $responseBody -ForegroundColor Gray
        } catch {
            Write-Host "Could not read response body" -ForegroundColor Yellow
        }
    }
    
    exit 1
}

