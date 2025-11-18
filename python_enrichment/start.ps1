# start.ps1 - Start AI Hub Enrichment Service
Write-Host "Starting AI Hub Enrichment Service on port 8001..." -ForegroundColor Green

# Check if required packages are installed
python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start the enrichment server using python -m (works even if uvicorn not in PATH)
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
