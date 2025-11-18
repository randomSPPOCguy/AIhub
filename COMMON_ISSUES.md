# Common Issues & Troubleshooting

Quick reference guide for common problems when setting up or running AIhub.

## 🚀 Setup Issues

### Issue: `npm install` fails or hangs

**Symptoms:**
- `npm install` takes a very long time or fails
- Error messages about missing dependencies

**Solutions:**
1. **Check Node.js version:**
   ```powershell
   node --version
   ```
   Should be **Node.js 18+**. If not, upgrade from [nodejs.org](https://nodejs.org/)

2. **Clear npm cache:**
   ```powershell
   npm cache clean --force
   npm install
   ```

3. **Delete node_modules and reinstall:**
   ```powershell
   Remove-Item -Recurse -Force node_modules
   Remove-Item package-lock.json
   npm install
   ```

4. **Use specific Node version (if using nvm):**
   ```powershell
   nvm install 18
   nvm use 18
   npm install
   ```

---

### Issue: Python dependencies fail to install

**Symptoms:**
- `pip install -r requirements.txt` fails
- Errors about missing C++ compiler or CUDA libraries

**Solutions:**
1. **Use virtual environment (recommended):**
   ```powershell
   # For python_ai/
   cd python_ai
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

   # For python_enrichment/
   cd python_enrichment
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install Visual C++ Build Tools (if onnxruntime fails):**
   - Download: [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
   - Install "Desktop development with C++" workload

3. **Use pre-built wheels (if CUDA issues):**
   ```powershell
   # CPU-only version (no CUDA needed)
   pip install onnxruntime onnxruntime-genai
   ```

---

### Issue: `config.env` not found

**Symptoms:**
- Error: "Cannot find config.env"
- Services fail to start

**Solution:**
1. Copy the example config:
   ```powershell
   Copy-Item config.env.example config.env
   ```

2. Edit `config.env` with your settings (API keys, ports, etc.)

3. See `docs/CONFIG_ENV.md` for detailed configuration options

---

## 🔌 Service Startup Issues

### Issue: Port already in use (3000, 8000, 8001)

**Symptoms:**
- Error: "EADDRINUSE: address already in use"
- Services won't start

**Solutions:**
1. **Find and kill the process:**
   ```powershell
   # Find process on port 3000
   netstat -ano | findstr :3000
   
   # Kill the process (replace PID with actual process ID)
   taskkill /PID <PID> /F
   ```

2. **Or change ports in `config.env`:**
   ```env
   PORT=3001
   PYTHON_AI_PORT=8001
   ENRICH_PORT=8002
   ```

3. **Check if services are already running:**
   ```powershell
   # Check Node.js server
   Get-Process node -ErrorAction SilentlyContinue
   
   # Check Python processes
   Get-Process python -ErrorAction SilentlyContinue
   ```

---

### Issue: Python services don't start

**Symptoms:**
- `python python_ai/server.py` fails
- `python python_enrichment/app.py` fails
- Import errors or missing modules

**Solutions:**
1. **Activate virtual environment:**
   ```powershell
   # For python_ai
   cd python_ai
   .venv\Scripts\activate
   python server.py

   # For python_enrichment
   cd python_enrichment
   .venv\Scripts\activate
   python app.py
   ```

2. **Check Python version:**
   ```powershell
   python --version
   ```
   Should be **Python 3.8+**. If not, upgrade from [python.org](https://www.python.org/)

3. **Reinstall dependencies:**
   ```powershell
   pip install -r requirements.txt --force-reinstall
   ```

---

### Issue: Services start but can't connect to each other

**Symptoms:**
- Node.js server can't reach Python AI service (port 8000)
- Enrichment service not responding (port 8001)
- 404 or connection refused errors

**Solutions:**
1. **Verify all services are running:**
   ```powershell
   # Check if services are listening
   netstat -ano | findstr ":3000 :8000 :8001"
   ```

2. **Test endpoints directly:**
   ```powershell
   # Test Python AI service
   Invoke-WebRequest http://localhost:8000/health

   # Test enrichment service
   Invoke-WebRequest http://localhost:8001/health
   ```

3. **Check firewall/antivirus:**
   - Windows Firewall may block local connections
   - Add exceptions for Node.js and Python
   - Some antivirus software blocks local servers

4. **Verify URLs in `config.env`:**
   ```env
   LOCAL_MODEL_URL=http://localhost:8000
   ENRICHMENT_URL=http://localhost:8001
   ```

---

## 🤖 AI Model Issues

### Issue: ONNX Runtime can't find CUDA/cuDNN

**Symptoms:**
- Error: "cudnn64_9.dll is missing"
- Error: "CUDAExecutionProvider not available"
- Model falls back to CPU (slow)

**Solutions:**
1. **Quick fix - Use CPU mode:**
   ```powershell
   cd python_ai
   .venv\Scripts\activate
   pip uninstall onnxruntime-gpu
   pip install onnxruntime onnxruntime-genai
   ```
   Update `config.env`:
   ```env
   LOCAL_MODEL_KIND=onnx-genai
   ```

2. **Install CUDA/cuDNN (for GPU acceleration):**
   - See detailed guide: `docs/TROUBLESHOOTING_CUDA.md`
   - Run diagnostic: `npm run check-cuda`
   - Or use setup wizard: `npm run setup`

3. **Use Ollama (easier alternative):**
   ```powershell
   # Install Ollama from ollama.com
   ollama pull phi3

   # Update config.env
   LOCAL_MODEL_KIND=ollama
   LOCAL_MODEL_URL=http://localhost:11434
   LOCAL_MODEL_NAME=phi3
   ```

---

### Issue: Model loads but responses are slow

**Symptoms:**
- Chat responses take 10+ seconds
- High CPU/GPU usage
- Timeout errors

**Solutions:**
1. **Check if using CPU instead of GPU:**
   ```powershell
   # In Python AI server terminal, look for:
   # "CPUExecutionProvider" = CPU (slow)
   # "CUDAExecutionProvider" = GPU (fast)
   ```

2. **Reduce model size:**
   - Use smaller model variant (phi3:mini instead of phi3)
   - Check `models/catalog.json` for available models

3. **Increase timeout in `config.env`:**
   ```env
   CHAT_TIMEOUT_MS=60000  # 60 seconds
   ```

4. **Check system resources:**
   ```powershell
   # Check CPU/GPU usage
   Get-Process python | Select-Object CPU, WorkingSet64
   ```

---

## 📡 API & Integration Issues

### Issue: API key authentication fails

**Symptoms:**
- 401 Unauthorized errors
- "Invalid API key" messages

**Solutions:**
1. **Generate a new API key:**
   ```powershell
   node bin/keygen.mjs -- --label your-label
   ```
   Copy the key (starts with `aih_`)

2. **Add key to request headers:**
   ```powershell
   $headers = @{
       "X-AIHub-Key" = "aih_your_key_here"
       "Content-Type" = "application/json"
   }
   ```

3. **Verify key format:**
   - Should start with `aih_`
   - Should be 32+ characters
   - No spaces or special characters (except underscore)

4. **Check key in database:**
   ```powershell
   # Use SQLite to check keys
   sqlite3 db/music.sqlite "SELECT * FROM api_keys;"
   ```

---

### Issue: Enrichment not working ("bot" keyword not triggering)

**Symptoms:**
- Queries like "bot who is radiohead?" don't get enriched
- No Wikipedia/MusicBrainz data in responses

**Solutions:**
1. **Verify enrichment service is running:**
   ```powershell
   # Check if service is up
   Invoke-WebRequest http://localhost:8001/health
   ```

2. **Check enrichment is enabled:**
   ```env
   # In config.env
   ENRICHMENT_ENABLED=true
   ENRICHMENT_URL=http://localhost:8001
   ```

3. **Test enrichment directly:**
   ```powershell
   $body = @{
       text = "bot who is radiohead?"
       room_id = "test"
   } | ConvertTo-Json

   Invoke-RestMethod -Uri "http://localhost:8001/enrich" `
       -Method POST `
       -Headers @{"Content-Type"="application/json"} `
       -Body $body
   ```

4. **Check logs for enrichment errors:**
   ```powershell
   # Look for enrichment logs in Node.js server output
   # Should see: [ENRICH] or [MUSIC] messages
   ```

---

## 🗄️ Database Issues

### Issue: Database migration fails

**Symptoms:**
- Error: "no such table"
- Migration errors when starting server

**Solutions:**
1. **Run migration manually:**
   ```powershell
   npm run migrate
   ```

2. **Delete and recreate database:**
   ```powershell
   Remove-Item db/music.sqlite
   npm run migrate
   ```

3. **Check schema file exists:**
   ```powershell
   Test-Path src/db/schema.sql
   ```

---

### Issue: Database locked or corrupted

**Symptoms:**
- "database is locked" errors
- "database disk image is malformed"

**Solutions:**
1. **Close all connections:**
   - Stop all running services
   - Close any SQLite database viewers

2. **Check for locks:**
   ```powershell
   # Kill any processes using the database
   Get-Process | Where-Object {$_.Path -like "*sqlite*"}
   ```

3. **Backup and recreate:**
   ```powershell
   Copy-Item db/music.sqlite db/music.sqlite.backup
   Remove-Item db/music.sqlite
   npm run migrate
   ```

---

## 🔍 Debugging Tips

### Enable verbose logging

**Edit `config.env`:**
```env
LOG_LEVEL=debug
LOG_FILE=logs/aihub.log
```

**Check logs:**
```powershell
# Real-time log viewing
Get-Content logs/aihub.log -Wait -Tail 50
```

---

### Test individual services

1. **Test Python AI service:**
   ```powershell
   cd python_ai
   .venv\Scripts\activate
   python server.py
   # Should show: "INFO:     Uvicorn running on http://0.0.0.0:8000"
   ```

2. **Test enrichment service:**
   ```powershell
   cd python_enrichment
   .venv\Scripts\activate
   python app.py
   # Should show: "INFO:     Uvicorn running on http://0.0.0.0:8001"
   ```

3. **Test Node.js server:**
   ```powershell
   npm start
   # Should show: "[INF] AI Hub 1.4.1 listening on :3000"
   ```

---

### Use diagnostic commands

```powershell
# Check CUDA setup
npm run check-cuda

# Run setup wizard
npm run setup

# Check hardware detection
node scripts/check-cuda.js
```

---

## 📚 More Help

- **Detailed CUDA/cuDNN issues:** See `docs/TROUBLESHOOTING_CUDA.md`
- **Known bugs:** See `docs/ISSUES.md`
- **Configuration:** See `docs/CONFIG_ENV.md`
- **Quick start:** See `docs/QUICK_START.md`
- **Project structure:** See `docs/PROJECT_NAVIGATION.md`

---

## 🐛 Still Having Issues?

1. **Check logs first:**
   - Node.js server logs (console output)
   - Python service logs (console output)
   - File logs: `logs/aihub.log` (if enabled)

2. **Gather system info:**
   ```powershell
   # Node.js version
   node --version
   
   # Python version
   python --version
   
   # OS version
   systeminfo | findstr /B /C:"OS Name" /C:"OS Version"
   
   # GPU info (if NVIDIA)
   nvidia-smi
   ```

3. **Create a minimal test case:**
   - Test each service individually
   - Check if issue is service-specific or integration-specific

4. **Check GitHub issues:**
   - Search existing issues in the repository
   - Create a new issue with:
     - Error messages (full stack trace)
     - Steps to reproduce
     - System information
     - Relevant log excerpts

---

**Last Updated:** 2025-01-17  
**Version:** 1.4.1 (Experimental Branch)

