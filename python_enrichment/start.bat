@echo off
echo Starting AI Hub Enrichment Service on port 8001...
cd /d "%~dp0"
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
