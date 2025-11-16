# Download Phi-3 Mini ONNX CUDA model using Hugging Face CLI
# This downloads all required files for ONNX GenAI

Write-Host "Installing huggingface-hub if needed..." -ForegroundColor Cyan
pip install -q huggingface-hub

Write-Host "`nDownloading Phi-3 Mini 4K Instruct ONNX INT4 CUDA model..." -ForegroundColor Green
Write-Host "This will download ~2.5GB to: models/downloads/phi-3-mini-onnx-cuda" -ForegroundColor Yellow

# Create download directory
New-Item -ItemType Directory -Force -Path "models\downloads\phi-3-mini-onnx-cuda" | Out-Null

# Download the model using huggingface-cli
huggingface-cli download `
  microsoft/Phi-3-mini-4k-instruct-onnx `
  --include "cuda/cuda-int4-rtn-block-32/*" `
  --local-dir "models\downloads\phi-3-mini-onnx-cuda" `
  --local-dir-use-symlinks False

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Download complete!" -ForegroundColor Green
    Write-Host "Model location: models\downloads\phi-3-mini-onnx-cuda\cuda\cuda-int4-rtn-block-32" -ForegroundColor Cyan

    # List downloaded files
    Write-Host "`nDownloaded files:" -ForegroundColor Yellow
    Get-ChildItem -Recurse "models\downloads\phi-3-mini-onnx-cuda" |
        Where-Object {!$_.PSIsContainer} |
        ForEach-Object {
            $size = if ($_.Length -gt 1GB) { "{0:N2} GB" -f ($_.Length / 1GB) }
                    elseif ($_.Length -gt 1MB) { "{0:N2} MB" -f ($_.Length / 1MB) }
                    elseif ($_.Length -gt 1KB) { "{0:N2} KB" -f ($_.Length / 1KB) }
                    else { "$($_.Length) bytes" }
            Write-Host "  $($_.FullName.Replace((Get-Location).Path + '\', '')) - $size"
        }
} else {
    Write-Host "`n✗ Download failed!" -ForegroundColor Red
    Write-Host "Make sure you have pip and huggingface-hub installed" -ForegroundColor Yellow
}
