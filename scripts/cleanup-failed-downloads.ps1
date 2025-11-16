# Clean up failed/incomplete downloads

Write-Host "Cleaning up failed downloads..." -ForegroundColor Yellow

# Remove the 15-byte failed download
$failedDir = "models\downloads\phi-3-mini-onnx-cuda"
if (Test-Path $failedDir) {
    Write-Host "Removing failed download: $failedDir" -ForegroundColor Cyan
    Remove-Item -Recurse -Force $failedDir
    Write-Host "✓ Cleaned up" -ForegroundColor Green
} else {
    Write-Host "No failed downloads found" -ForegroundColor Gray
}

Write-Host "`nReady for fresh download!" -ForegroundColor Green
