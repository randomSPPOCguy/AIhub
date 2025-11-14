"""
Additional API endpoints for AIHub Unified
Settings and Model Management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import aiohttp
import asyncio
from pathlib import Path

router = APIRouter()

# API Keys management
class APIKeyUpdate(BaseModel):
    provider: str
    api_key: str

@router.get("/api/settings/keys")
async def get_api_keys_status():
    """Check which API keys are configured"""
    env_path = Path(__file__).parent / '.env'
    keys_set = {
        'openai_set': False,
        'claude_set': False,
        'gemini_set': False
    }
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            keys_set['openai_set'] = 'OPENAI_API_KEY=' in content and len(content.split('OPENAI_API_KEY=')[1].split('\n')[0].strip()) > 0
            keys_set['claude_set'] = 'CLAUDE_API_KEY=' in content and len(content.split('CLAUDE_API_KEY=')[1].split('\n')[0].strip()) > 0
            keys_set['gemini_set'] = 'GEMINI_API_KEY=' in content and len(content.split('GEMINI_API_KEY=')[1].split('\n')[0].strip()) > 0
    
    return keys_set

@router.post("/api/settings/keys")
async def update_api_key(key_update: APIKeyUpdate):
    """Update an API key in .env file"""
    env_path = Path(__file__).parent / '.env'
    
    # Map provider to env var name
    env_var_map = {
        'openai': 'OPENAI_API_KEY',
        'claude': 'CLAUDE_API_KEY',
        'gemini': 'GEMINI_API_KEY'
    }
    
    if key_update.provider not in env_var_map:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    env_var = env_var_map[key_update.provider]
    
    # Read current .env
    lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    
    # Update or add the key
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_var}="):
            lines[i] = f"{env_var}={key_update.api_key}\n"
            found = True
            break
    
    if not found:
        lines.append(f"{env_var}={key_update.api_key}\n")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    # Update environment variable for current process
    os.environ[env_var] = key_update.api_key
    
    return {"success": True, "message": f"{key_update.provider} API key updated"}

@router.delete("/api/settings/keys/{provider}")
async def remove_api_key(provider: str):
    """Remove an API key from .env file"""
    env_path = Path(__file__).parent / '.env'
    
    env_var_map = {
        'openai': 'OPENAI_API_KEY',
        'claude': 'CLAUDE_API_KEY',
        'gemini': 'GEMINI_API_KEY'
    }
    
    if provider not in env_var_map:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    env_var = env_var_map[provider]
    
    if not env_path.exists():
        return {"success": True, "message": "No .env file found"}
    
    # Read and filter lines
    with open(env_path, 'r') as f:
        lines = [line for line in f.readlines() if not line.startswith(f"{env_var}=")]
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    # Remove from environment
    if env_var in os.environ:
        del os.environ[env_var]
    
    return {"success": True, "message": f"{provider} API key removed"}


# Model Management
class ModelDownload(BaseModel):
    model_id: str
    name: str
    url: str

# Track download progress
download_progress = {}

# Disabled - using Phase 1 model_manager download system instead
# @router.post("/api/models/download")
async def download_model_old(model: ModelDownload):
    """Download a model file"""
    models_dir = Path(__file__).parent / 'models'
    models_dir.mkdir(exist_ok=True)
    
    # Sanitize filename
    filename = f"{model.model_id}.gguf"
    filepath = models_dir / filename
    
    # Initialize progress
    download_progress[model.model_id] = 0
    
    # Start download in background
    asyncio.create_task(_download_file(model.url, filepath, model.model_id))
    
    return {"success": True, "message": "Download started", "model_id": model.model_id}

async def _download_file(url: str, filepath: Path, model_id: str):
    """Background task to download file with progress"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    download_progress[model_id] = -1
                    return
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            download_progress[model_id] = progress
        
        # Mark as complete
        download_progress[model_id] = 100
        
        # Register the model
        # TODO: Add to registered models
        
    except Exception as e:
        print(f"Download error: {e}")
        download_progress[model_id] = -1

@router.get("/api/models/download/{model_id}/progress")
async def get_download_progress(model_id: str):
    """Get download progress for a model"""
    progress = download_progress.get(model_id, 0)
    return {"model_id": model_id, "progress": progress}

@router.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    """Delete a downloaded model"""
    models_dir = Path(__file__).parent / 'models'
    filepath = models_dir / f"{model_id}.gguf"
    
    if filepath.exists():
        filepath.unlink()
        return {"success": True, "message": "Model deleted"}
    else:
        raise HTTPException(status_code=404, detail="Model not found")
