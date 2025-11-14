"""
AI Hub - Unified interface for multiple AI providers
Supports: Gemini, OpenAI, Claude
Includes Wikipedia, MusicBrainz, and WebSocket support
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, Security, Depends, BackgroundTasks, WebSocketDisconnect
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
import json
import os
import asyncio
from collections import defaultdict

from providers.cloud.gemini_provider import GeminiProvider
from providers.cloud.openai_provider import OpenAIProvider
from providers.cloud.claude_provider import ClaudeProvider
from config import settings

# Local models (transformers) - optional, loads ANY HuggingFace model
try:
    from providers.local_model_provider import LocalModelProvider
    LOCAL_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Local model provider not available: {e}")
    print("   Install with: pip install transformers torch accelerate")
    LOCAL_MODELS_AVAILABLE = False
    LocalModelProvider = None
from services import wikipedia_service, musicbrainz_service
from websocket.room_handler import websocket_room_endpoint
try:
    from tools_api import router as tools_router
except Exception:
    # Fallback when running as a package where tools folder is a module
    from tools.tools_api import router as tools_router
from music_info_processor import MusicInfoProcessor
import pathlib
import time

# ONNX Runtime integration
try:
    from onnx_engine import status as onnx_status, build_session_if_configured
    ONNX_ENABLED = True
except ImportError as e:
    print(f"⚠️ ONNX Runtime not available: {e}")
    ONNX_ENABLED = False

# New imports for Phase 1
try:
    from model_manager import model_manager
    from logging_manager import (
        setup_logging, 
        get_current_log_level, 
        set_log_level,
        get_log_levels,
        api_call_logger,
        log_info, 
        log_debug, 
        log_error
    )
    from service_manager import service_manager, auto_load_services
    PHASE_1_ENABLED = True
except ImportError as e:
    print(f"⚠️ Phase 1 features not available: {e}")
    PHASE_1_ENABLED = False

# Model loader for tracking in-memory loading progress
try:
    from model_loader import model_loader
except Exception:
    model_loader = None

MODELS_REGISTRY_DIR = os.path.join(os.path.dirname(__file__), 'models')
if not os.path.exists(MODELS_REGISTRY_DIR):
    os.makedirs(MODELS_REGISTRY_DIR, exist_ok=True)
MODELS_REGISTRY_FILE = os.path.join(MODELS_REGISTRY_DIR, 'registered_models.json')

def _read_registered_models() -> List[Dict[str, Any]]:
    try:
        if not os.path.exists(MODELS_REGISTRY_FILE):
            return []
        with open(MODELS_REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _write_registered_models(models: List[Dict[str, Any]]):
    try:
        with open(MODELS_REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(models, f, indent=2)
    except Exception as e:
        print('Failed to write registered models:', e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.
    Initializes ONNX Runtime, logging, and services.
    """
    global _phi3_instance, _phi3_selected_model
    
    # Initialize logging system if Phase 1 is enabled
    if PHASE_1_ENABLED:
        setup_logging("INFO")
        log_info("AI Hub starting up...", category="app")
    else:
        print("=" * 50)
        print("[STARTUP] AI Hub Backend Ready")
        print("[STARTUP] Phi-3 will load on first use")
        print("=" * 50)
    
    # Initialize ONNX Runtime if enabled
    if ONNX_ENABLED and settings.USE_ONNX:
        if PHASE_1_ENABLED:
            log_info("Initializing ONNX Runtime...", category="app")
        else:
            print("[STARTUP] Initializing ONNX Runtime...")
        
        onnx_dir = settings.ONNX_MODEL_DIR or ""
        app.state.onnx_status = onnx_status(
            onnx_dir,
            settings.ONNX_EXECUTION_PROVIDER,
            settings.ONNX_ENABLE_TRT
        )
        
        # Only build session if path exists and is non-empty
        model_path = None
        if onnx_dir and os.path.exists(onnx_dir):
            # Check if it's a directory or file
            if os.path.isdir(onnx_dir):
                import glob
                onnx_files = glob.glob(os.path.join(onnx_dir, "*.onnx"))
                if onnx_files:
                    model_path = onnx_files[0]  # Use the first .onnx file found
            elif os.path.isfile(onnx_dir) and onnx_dir.endswith('.onnx'):
                model_path = onnx_dir
        
        app.state.onnx_session = build_session_if_configured(
            model_path,
            settings.ONNX_EXECUTION_PROVIDER,
            settings.ONNX_ENABLE_TRT
        )
        
        if app.state.onnx_session:
            if PHASE_1_ENABLED:
                log_info("✅ ONNX Runtime ready with model!", category="app")
            else:
                print("[STARTUP] ✅ ONNX Runtime ready with model!")
        else:
            if PHASE_1_ENABLED:
                log_info("ℹ️ ONNX Runtime ready (no model configured)", category="app")
            else:
                print("[STARTUP] ℹ️ ONNX Runtime ready (no model configured)")
    else:
        app.state.onnx_status = None
        app.state.onnx_session = None
    
    # Don't load Phi-3 here - let it load on-demand when first chat happens
    _phi3_instance = None
    _phi3_selected_model = None
    
    # Auto-load services if Phase 1 is enabled
    if PHASE_1_ENABLED:
        log_info("Auto-loading services...", category="app")
        await auto_load_services()
        log_info("✅ AI Hub is ready!", category="app")
    else:
        print("[STARTUP] Wikipedia and MusicBrainz services available")
    
    # Local model preloading DISABLED - models will be loaded on-demand via the model management UI
    # Users can download and configure ANY HuggingFace model through the app interface
    if LOCAL_MODELS_AVAILABLE:
        if PHASE_1_ENABLED:
            log_info("ℹ️ Local models available - download any model on-demand", category="app")
        else:
            print("[STARTUP] ℹ️ Local models available - download any model on-demand")
    else:
        if PHASE_1_ENABLED:
            log_info("ℹ️ Local models not available - install transformers/torch to enable", category="app")
        else:
            print("[STARTUP] ℹ️ Local models not available - install transformers/torch to enable")
    
    yield
    
    # Shutdown: cleanup resources
    if PHASE_1_ENABLED:
        log_info("AI Hub shutting down...", category="app")


app = FastAPI(
    title="AI Hub",
    description="Unified API for multiple AI providers with information tools",
    version="1.0.0",
    lifespan=lifespan
)

# API Key Security (optional)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key if BOT_API_KEY is configured."""
    # If no API key is configured in settings, allow all requests
    if not settings.BOT_API_KEY:
        return None
    
    # If API key is configured, require it
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Please provide X-API-Key header."
        )
    
    if api_key != settings.BOT_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return api_key

# Include tools API routes
app.include_router(tools_router, prefix="/api/tools", tags=["tools"])

# Include API extensions (settings, model management)
try:
    from api_extensions import router as extensions_router
    app.include_router(extensions_router, tags=["extensions"])
except ImportError:
    print("⚠️ API extensions not available")


# ============================================================================
# ONNX RUNTIME SYSTEM ENDPOINTS
# ============================================================================

@app.get("/system/providers")
async def get_onnx_providers():
    """
    Get ONNX Runtime provider information.
    Returns available providers, requested providers, and configuration status.
    """
    if not ONNX_ENABLED:
        return {
            "onnx_available": False,
            "error": "ONNX Runtime not installed"
        }
    
    if not settings.USE_ONNX:
        return {
            "onnx_available": True,
            "enabled": False,
            "message": "ONNX Runtime installed but not enabled (set USE_ONNX=true)"
        }
    
    status_info = app.state.onnx_status if hasattr(app.state, 'onnx_status') else None
    if status_info:
        return status_info
    
    # Fallback if status not in app state
    return onnx_status(
        settings.ONNX_MODEL_DIR,
        settings.ONNX_EXECUTION_PROVIDER,
        settings.ONNX_ENABLE_TRT
    )


@app.get("/system/onnx/ready")
async def onnx_ready():
    """
    Check if ONNX Runtime is ready for inference.
    Returns ready status and provider information.
    """
    if not ONNX_ENABLED:
        return {
            "ready": False,
            "error": "ONNX Runtime not installed"
        }
    
    if not settings.USE_ONNX:
        return {
            "ready": False,
            "enabled": False,
            "message": "ONNX Runtime not enabled"
        }
    
    status_info = app.state.onnx_status if hasattr(app.state, 'onnx_status') else None
    has_session = hasattr(app.state, 'onnx_session') and app.state.onnx_session is not None
    
    result = {
        "ready": has_session,
        "has_model": has_session,
    }
    
    if status_info:
        result.update({
            "providers": status_info.get("available_providers", []),
            "requested": status_info.get("requested_providers", []),
            "warnings": status_info.get("warnings", []),
        })
    
    return result


@app.post("/system/onnx/generate")
async def onnx_generate_stub():
    """
    Placeholder endpoint for ONNX model generation.
    Returns 503 if no model is configured.
    
    This endpoint will be implemented once you add a local ONNX model.
    """
    if not ONNX_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="ONNX Runtime not installed"
        )
    
    if not settings.USE_ONNX:
        raise HTTPException(
            status_code=503,
            detail="ONNX Runtime not enabled"
        )
    
    has_session = hasattr(app.state, 'onnx_session') and app.state.onnx_session is not None
    
    if not has_session:
        raise HTTPException(
            status_code=503,
            detail="ONNX model not configured on this machine. Set ONNX_MODEL_DIR to enable."
        )
    
    return {
        "ok": True,
        "note": "Model hooked up; implement generate() when you add generation logic."
    }


# ============================================================================
# END ONNX RUNTIME ENDPOINTS
# ============================================================================

# Mount static files if directory exists
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize providers
providers = {
    "gemini": GeminiProvider(settings.GEMINI_API_KEY),
    "openai": OpenAIProvider(settings.OPENAI_API_KEY),
    "claude": ClaudeProvider(settings.CLAUDE_API_KEY),
}

# Initialize music info processor (Local Model + main AI)
music_processor = None
if settings.USE_PHI3_FOR_INFO and LOCAL_MODELS_AVAILABLE:
    try:
        music_processor = MusicInfoProcessor()
    except Exception as e:
        print(f"⚠️ Failed to initialize Phi-3: {e}")
        print("Music info processing will be disabled")

# Lazy-loaded local model instance for direct local-chat requests
_local_model_instance = None

# track selected local model name
_selected_model_name: Optional[str] = None

async def get_local_model_instance(model: Optional[str] = None):
    global _local_model_instance, _selected_model_name
    
    if not LOCAL_MODELS_AVAILABLE:
        raise ValueError(
            "Local models not available. Install with: pip install transformers torch accelerate"
        )
    
    if model:
        # If model requested differs from current, recreate
        if _local_model_instance is None or model != _selected_model_name:
            _local_model_instance = LocalModelProvider(model_name=model)
            await _local_model_instance.initialize()  # Async initialization
            _selected_model_name = model
    else:
        if _local_model_instance is None:
            # Use default from settings if available
            default_model = (getattr(settings, "LOCAL_PHI3_MODELS", "") or "").split(",")[0].strip() or "microsoft/Phi-3-mini-4k-instruct"
            _local_model_instance = LocalModelProvider(model_name=default_model)
            await _local_model_instance.initialize()  # Async initialization
            _selected_model_name = default_model
    return _local_model_instance


@app.post("/api/set_local_model")
async def set_local_model(payload: dict):
    """Set the active local model and reinitialize the provider.

    Body: { "model": "model_name" }
    """
    if not LOCAL_MODELS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Local models not available. Install with: pip install transformers torch accelerate"
        )
    
    model = (payload or {}).get("model")
    if not model:
        raise HTTPException(status_code=400, detail="Missing model name")
    try:
        # Recreate the local model instance with the requested model
        await get_local_model_instance(model=model)
        return {"ok": True, "model": model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set model: {e}")

# In-memory conversation store: conversation_id -> list[Message]
# conversation_id can be a room id or any key provided by clients
chat_histories: Dict[str, List[Dict[str, str]]] = defaultdict(list)


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    provider: Literal["gemini", "openai", "claude"]
    messages: List[Message]
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=4096)
    stream: bool = False


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: Optional[Dict[str, Any]] = None


class IngestChatRequest(BaseModel):
    room_id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    bot_user_id: Optional[str] = None
    text: str
    provider: Optional[Literal["gemini", "openai", "claude"]] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)


class IngestChatResponse(BaseModel):
    triggered: bool
    content: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


@app.get("/")
async def root():
    """Serve the test interface HTML"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    
    return {
        "name": "AI Hub",
        "version": "1.0.0",
        "providers": list(providers.keys()),
        "endpoints": {
            "chat": "/api/chat",
            "health": "/health",
            "detailed_health": "/api/health",
            "providers": "/api/providers"
        },
        "message": "Web interface not found. Access API docs at /docs"
    }


@app.get("/health")
async def simple_health_check():
    """Simple fast health check - just confirms the server is running"""
    print("[HEALTH] Health check received")
    return {"status": "ok"}


@app.get("/api/health")
async def health_check():
    """Detailed health check of all providers"""
    status = {}
    for name, provider in providers.items():
        try:
            is_healthy = await provider.health_check()
            status[name] = "healthy" if is_healthy else "unhealthy"
        except Exception as e:
            status[name] = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "providers": status
    }


@app.get("/api/debug/provider")
async def debug_provider_info(api_key: str = Depends(verify_api_key)):
    """
    Debug endpoint to show which local_model_provider module is loaded
    and the model's device placement
    """
    import sys
    import inspect
    try:
        import torch
        import transformers
        torch_version = torch.__version__
        transformers_version = transformers.__version__
    except Exception:
        torch_version = "Not installed"
        transformers_version = "Not installed"
    
    try:
        import providers.local_model_provider as _pp
        
        info = {
            "python_executable": sys.executable,
            "torch_version": torch_version,
            "transformers_version": transformers_version,
            "local_model_provider_file": _pp.__file__,
            "chat_method_first_line": inspect.getsource(_pp.LocalModelProvider.chat).splitlines()[0] if hasattr(_pp.LocalModelProvider, 'chat') else "N/A",
        }
        
        # If instance exists, get device map
        global _local_model_instance
        if _local_model_instance:
            if hasattr(_local_model_instance, 'model') and hasattr(_local_model_instance.model, 'hf_device_map'):
                info["device_map"] = str(_local_model_instance.model.hf_device_map)
            else:
                info["device_map"] = "N/A"
            info["instance_exists"] = True
        else:
            info["instance_exists"] = False
            info["device_map"] = "No instance loaded yet"
            
        return info
    except Exception as e:
        return {"error": str(e)}


@app.get("/phi3/status")
async def local_model_status():
    """
    Get local model loading status for loading indicator UI
    """
    global _local_model_instance
    
    if not LOCAL_MODELS_AVAILABLE:
        return {
            "status": "not_available",
            "message": "Local model dependencies not installed (transformers/torch)",
            "ready": False,
            "available": False
        }
    
    if _local_model_instance is None:
        return {
            "status": "not_loaded",
            "message": "Model not loaded yet",
            "ready": False,
            "available": True
        }
    
    if _local_model_instance.is_loading:
        return {
            "status": "loading",
            "message": "Local AI model is loading...",
            "ready": False,
            "available": True
        }
    
    if _local_model_instance.load_error:
        return {
            "status": "error",
            "message": f"Model failed to load: {_local_model_instance.load_error}",
            "ready": False,
            "available": True
        }
    
    return {
        "status": "ready",
        "message": "Local AI model is ready!",
        "ready": True,
        "available": True
    }


# ============================================================================
# NEW API SERVICE ENDPOINTS
# ============================================================================

@app.get("/api/weather/forecast")
async def get_weather_forecast(lat: float, lon: float, api_key: str = Depends(verify_api_key)):
    """Get 7-day weather forecast for coordinates"""
    service = service_manager.get_service("noaa_weather")
    if not service:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    
    try:
        forecast = await service.get_forecast_by_coords(lat, lon)
        if forecast is None:
            raise HTTPException(status_code=404, detail="Forecast not found for coordinates")
        return {"success": True, "data": forecast}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weather/hourly")
async def get_weather_hourly(lat: float, lon: float, api_key: str = Depends(verify_api_key)):
    """Get hourly weather forecast for coordinates"""
    service = service_manager.get_service("noaa_weather")
    if not service:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    
    try:
        forecast = await service.get_hourly_forecast(lat, lon)
        if forecast is None:
            raise HTTPException(status_code=404, detail="Hourly forecast not found")
        return {"success": True, "data": forecast}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weather/alerts")
async def get_weather_alerts(lat: float, lon: float, api_key: str = Depends(verify_api_key)):
    """Get active weather alerts for coordinates"""
    service = service_manager.get_service("noaa_weather")
    if not service:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    
    try:
        alerts = await service.get_active_alerts(lat, lon)
        return {"success": True, "data": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tv/search")
async def search_tv_shows(q: str, api_key: str = Depends(verify_api_key)):
    """Search TV shows by title"""
    service = service_manager.get_service("tvmaze")
    if not service:
        raise HTTPException(status_code=503, detail="TV service unavailable")
    
    try:
        results = await service.search_shows(q)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tv/show/{show_id}")
async def get_tv_show_details(show_id: int, api_key: str = Depends(verify_api_key)):
    """Get TV show details by ID"""
    service = service_manager.get_service("tvmaze")
    if not service:
        raise HTTPException(status_code=503, detail="TV service unavailable")
    
    try:
        details = await service.get_show_details(show_id)
        if details is None:
            raise HTTPException(status_code=404, detail="Show not found")
        return {"success": True, "data": details}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tv/show/{show_id}/episodes")
async def get_tv_episodes(show_id: int, api_key: str = Depends(verify_api_key)):
    """Get all episodes for a TV show"""
    service = service_manager.get_service("tvmaze")
    if not service:
        raise HTTPException(status_code=503, detail="TV service unavailable")
    
    try:
        episodes = await service.get_episodes(show_id)
        return {"success": True, "data": episodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tv/show/{show_id}/cast")
async def get_tv_cast(show_id: int, api_key: str = Depends(verify_api_key)):
    """Get cast for a TV show"""
    service = service_manager.get_service("tvmaze")
    if not service:
        raise HTTPException(status_code=503, detail="TV service unavailable")
    
    try:
        cast = await service.get_cast(show_id)
        return {"success": True, "data": cast}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries/all")
async def get_all_countries(fields: str = None, api_key: str = Depends(verify_api_key)):
    """Get all countries (optional field filtering)"""
    service = service_manager.get_service("rest_countries")
    if not service:
        raise HTTPException(status_code=503, detail="Countries service unavailable")
    
    try:
        fields_list = fields.split(",") if fields else None
        countries = await service.get_all_countries(fields_list)
        return {"success": True, "data": countries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries/search")
async def search_countries(name: str = None, region: str = None, code: str = None, api_key: str = Depends(verify_api_key)):
    """Search countries by name, region, or code"""
    service = service_manager.get_service("rest_countries")
    if not service:
        raise HTTPException(status_code=503, detail="Countries service unavailable")
    
    try:
        if code:
            result = await service.get_country_by_code(code)
            if result is None:
                raise HTTPException(status_code=404, detail="Country not found")
            return {"success": True, "data": result}
        elif name:
            result = await service.get_country_by_name(name)
            if result is None:
                raise HTTPException(status_code=404, detail="Country not found")
            return {"success": True, "data": result}
        elif region:
            result = await service.get_countries_by_region(region)
            return {"success": True, "data": result}
        else:
            result = await service.get_all_countries()
            return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries/currency/{currency}")
async def get_countries_by_currency(currency: str, api_key: str = Depends(verify_api_key)):
    """Get countries by currency code"""
    service = service_manager.get_service("rest_countries")
    if not service:
        raise HTTPException(status_code=503, detail="Countries service unavailable")
    
    try:
        countries = await service.get_countries_by_currency(currency)
        return {"success": True, "data": countries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/search")
async def search_books(q: str, limit: int = 10, api_key: str = Depends(verify_api_key)):
    """Search books by title, author, or ISBN"""
    service = service_manager.get_service("open_library")
    if not service:
        raise HTTPException(status_code=503, detail="Books service unavailable")
    
    try:
        results = await service.search_books(q, limit)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/isbn/{isbn}")
async def get_book_by_isbn(isbn: str, api_key: str = Depends(verify_api_key)):
    """Get book details by ISBN"""
    service = service_manager.get_service("open_library")
    if not service:
        raise HTTPException(status_code=503, detail="Books service unavailable")
    
    try:
        result = await service.search_by_isbn(isbn)
        if result is None:
            raise HTTPException(status_code=404, detail="Book not found")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/author/{author}")
async def search_books_by_author(author: str, limit: int = 10, api_key: str = Depends(verify_api_key)):
    """Search books by author"""
    service = service_manager.get_service("open_library")
    if not service:
        raise HTTPException(status_code=503, detail="Books service unavailable")
    
    try:
        results = await service.search_by_author(author, limit)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trivia/questions")
async def get_trivia_questions(
    amount: int = 10, 
    category: int = None, 
    difficulty: str = None,
    qtype: str = "multiple",
    api_key: str = Depends(verify_api_key)
):
    """Get trivia questions"""
    service = service_manager.get_service("open_trivia")
    if not service:
        raise HTTPException(status_code=503, detail="Trivia service unavailable")
    
    try:
        result = await service.get_questions(amount, category, difficulty, qtype)
        
        # Check response code (0 = success)
        if result.get('response_code') != 0:
            error_msgs = {
                1: "No Results: Could not return results. The API doesn't have enough questions for your query.",
                2: "Invalid Parameter: Contains an invalid parameter. Arguements passed in aren't valid.",
                3: "Token Not Found: Session Token does not exist.",
                4: "Token Empty: Session Token has returned all possible questions for the specified query.",
                5: "Rate Limit: Too many requests. Only 1 request every 5 seconds."
            }
            error_msg = error_msgs.get(result.get('response_code'), "Unknown error")
            raise HTTPException(status_code=400, detail=error_msg)
        
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trivia/categories")
async def get_trivia_categories(api_key: str = Depends(verify_api_key)):
    """Get list of trivia categories"""
    service = service_manager.get_service("open_trivia")
    if not service:
        raise HTTPException(status_code=503, detail="Trivia service unavailable")
    
    try:
        categories = await service.get_categories()
        return {"success": True, "data": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/providers")
async def get_providers():
    """Get available providers and their models"""
    provider_info = {}
    for name, provider in providers.items():
        provider_info[name] = {
            "available": provider.is_configured(),
            "models": provider.get_available_models()
        }
    return provider_info


@app.post("/api/chat")
async def chat(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    """
    Unified chat endpoint for all providers
    
    Supports both streaming and non-streaming responses
    """
    # Validate provider
    if request.provider not in providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Choose from: {list(providers.keys())}"
        )
    
    provider = providers[request.provider]
    
    # Check if provider is configured
    if not provider.is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"{request.provider} is not configured. Please set API key."
        )
    
    # Convert messages to dict format
    messages = [msg.dict() for msg in request.messages]
    # Inject centralized personality if no system message was provided
    if not any(m.get("role") == "system" for m in messages):
        if settings.DEFAULT_PERSONALITY:
            messages = ([
                {"role": "system", "content": settings.DEFAULT_PERSONALITY}
            ] + messages)
    
    try:
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in provider.chat_stream(
                    messages=messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            response = await provider.chat(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            return ChatResponse(
                provider=request.provider,
                model=response.get("model", request.model or "unknown"),
                content=response["content"],
                usage=response.get("usage")
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error from {request.provider}: {str(e)}"
        )


def _get_keywords() -> List[str]:
    raw = (settings.BOT_KEYWORDS or "").strip()
    if not raw:
        return []
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _contains_keyword(text: str) -> bool:
    text_l = (text or "").lower()
    for k in _get_keywords():
        if k and k in text_l:
            return True
    return False


def _ensure_personality(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if any(m.get("role") == "system" for m in messages):
        return messages
    if settings.DEFAULT_PERSONALITY:
        return ([{"role": "system", "content": settings.DEFAULT_PERSONALITY}] + messages)
    return messages


@app.post("/api/ingest/chat")
async def ingest_chat(req: IngestChatRequest):
    """Ingest a chat line from a bot client.

    - Tracks per-conversation history (by conversation_id or room_id)
    - Detects keywords centrally (settings.BOT_KEYWORDS)
    - If triggered, generates a reply using configured provider/model
    - Returns {triggered: bool, content?: str}
    """
    conversation_id = req.conversation_id or req.room_id or "default"

    # Ignore self messages if possible
    if req.bot_user_id and req.user_id and str(req.bot_user_id) == str(req.user_id):
        return IngestChatResponse(triggered=False)

    # Append user message to history
    history = chat_histories[conversation_id]
    history.append({"role": "user", "content": req.text})
    # Trim history
    if len(history) > settings.DEFAULT_HISTORY_LIMIT * 2:
        del history[: len(history) - settings.DEFAULT_HISTORY_LIMIT * 2]

    if not _contains_keyword(req.text):
        return IngestChatResponse(triggered=False)

    # Select provider
    provider_name = req.provider or "gemini"
    if provider_name not in providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider_name}")
    provider = providers[provider_name]
    if not provider.is_configured():
        raise HTTPException(status_code=503, detail=f"{provider_name} is not configured. Set API key.")

    # Build messages for model: include system personality + history
    messages = _ensure_personality(history.copy())

    try:
        response = await provider.chat(
            messages=messages,
            model=req.model,
            temperature=req.temperature if req.temperature is not None else 0.7,
            max_tokens=req.max_tokens if req.max_tokens is not None else 300,
        )
        content = response.get("content")

        # Append assistant reply to history
        if content:
            history.append({"role": "assistant", "content": content})

        return IngestChatResponse(
            triggered=True,
            content=content or "",
            provider=provider_name,
            model=response.get("model", req.model or "unknown"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error from {provider_name}: {str(e)}")


# Simple model registration endpoints used by the JS modelProxy after downloads finish
@app.post('/api/models/register')
async def register_model(payload: Dict[str, Any]):
    """Register a downloaded model so it appears in `GET /api/local_models`.

    Expected payload: { id, path, name?, size? }
    The `path` should be an absolute path that the Python process can access.
    This endpoint will verify the path exists and add an entry to a local registry.
    """
    if not payload:
        raise HTTPException(status_code=400, detail='Missing payload')
    model_id = payload.get('id')
    model_path = payload.get('path')
    model_name = payload.get('name') or model_id
    model_size = payload.get('size')

    if not model_id or not model_path:
        raise HTTPException(status_code=400, detail='Missing id or path')

    # Normalize and verify path
    model_path_norm = os.path.abspath(model_path)
    if not os.path.exists(model_path_norm):
        raise HTTPException(status_code=400, detail=f'Path does not exist: {model_path_norm}')

    models = _read_registered_models()
    # avoid duplicates
    exists = any(m.get('id') == model_id or m.get('path') == model_path_norm for m in models)
    if not exists:
        entry = {
            'id': model_id,
            'name': model_name,
            'path': model_path_norm,
            'size': model_size,
            'added_at': int(time.time())
        }
        models.append(entry)
        _write_registered_models(models)

    return { 'ok': True, 'id': model_id, 'path': model_path_norm }


@app.get('/api/local_models')
async def list_local_models():
    """Return a list of configured/available local models (Phi-3)."""
    models = _read_registered_models()
    # Also expose any models listed in settings.LOCAL_PHI3_MODELS (comma-separated)
    raw = getattr(settings, 'LOCAL_PHI3_MODELS', '') or ''
    cfg_models = [s.strip() for s in raw.split(',') if s.strip()]
    
    # Combine registered model IDs with configured models
    all_model_names = [m.get('id', m.get('name', '')) for m in models] + cfg_models
    
    # Return format expected by frontend
    return { 'models': all_model_names }


@app.post("/api/chat/{provider}")
async def chat_provider_specific(provider: str, request: ChatRequest):
    """
    Provider-specific chat endpoint
    (Legacy support - prefer /api/chat with provider field)
    """
    request.provider = provider
    return await chat(request)


# ============================================================
# Music Information Processing Endpoints (Phi-3 + APIs)
# ============================================================

class MusicInfoRequest(BaseModel):
    artist: str
    title: str
    album: Optional[str] = None


class MusicChatRequest(BaseModel):
    message: str
    song_data: Optional[Dict[str, str]] = None
    provider: Optional[Literal["gemini", "openai", "claude"]] = "gemini"


@app.post("/api/music/info")
async def get_music_info(request: MusicInfoRequest):
    """
    Get processed music information using Phi-3 + Wikipedia + MusicBrainz
    
    Phi-3 processes the API data and returns a concise summary
    """
    if not music_processor:
        raise HTTPException(
            status_code=503,
            detail="Music info processing not available (Phi-3 not initialized)"
        )
    
    try:
        song_data = {
            "artist": request.artist,
            "title": request.title,
            "album": request.album
        }
        
        summary = await music_processor.process_now_playing(song_data)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Music info error: {str(e)}")


@app.post("/api/music/chat")
async def music_chat(request: MusicChatRequest):
    """
    Chat with music context
    
    - Phi-3 processes song info from Wikipedia + MusicBrainz
    - Main AI provider (Gemini/Claude/OpenAI) responds with that context
    """
    if not music_processor:
        raise HTTPException(
            status_code=503,
            detail="Music info processing not available (Phi-3 not initialized)"
        )
    
    try:
        song_context = None
        
        if request.song_data:
            # Get info about current song using Phi-3
            song_context = await music_processor.process_now_playing(request.song_data)
        
        # Get the requested provider
        provider = providers.get(request.provider)
        if not provider:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")
        
        # Build messages with song context
        messages = []
        if song_context:
            messages.append({
                "role": "system",
                "content": f"Current song context:\n{song_context}\n\nUse this info to answer questions about the music."
            })
        
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        # Use main AI to respond
        response = await provider.chat(messages=messages)
        
        return {
            "response": response.get("content"),
            "context": song_context,
            "provider": request.provider
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Music chat error: {str(e)}")


class LocalChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]


@app.post("/api/local_chat")
async def local_chat(req: LocalChatRequest, api_key: str = Depends(verify_api_key)):
    """Chat using a local model installed on this machine.

    This endpoint will lazy-load the model provider on first use. The request body should be:
      { "model": "microsoft/...", "messages": [{"role":"user","content":"..."}, ...] }
    """
    if not LOCAL_MODELS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Local models not available. Install with: pip install transformers torch accelerate"
        )
    
    try:
        # Determine which model to use
        # If req.model is a HuggingFace ID, use it directly
        # If it's a model_id (like "qwen2-3b"), look it up in the registry
        model_to_use = req.model
        model_config = None
        
        if req.model:
            # Check if this is a model_id (short name) or HuggingFace ID (has /)
            if '/' not in req.model:
                # This is a model_id, look it up
                model_id = req.model
                model_info = model_manager.get_model_by_id(model_id)
                if model_info:
                    model_to_use = model_info.get('huggingface_id')
                    log_info(f"Resolved model_id '{model_id}' to HuggingFace ID: {model_to_use}", category="chat")
            else:
                # This is already a HuggingFace ID, try to find the model_id for config
                model_id = req.model.split('/')[-1].lower().replace('-instruct', '').replace('_', '-')
            
            # Load saved model configuration
            log_info(f"Loading config for model_id: {model_id}", category="chat")
            model_config = model_manager.get_model_config(model_id)
            if model_config:
                log_info(f"✓ Using saved config: temp={model_config.get('temperature')}, max_tokens={model_config.get('max_tokens')}", category="chat")
            else:
                log_info(f"No saved config found for {model_id}, using defaults", category="chat")
        
        # Get the model instance (this will load the correct model)
        local_model = await get_local_model_instance(model=model_to_use)
        
        # Apply configuration if available
        if model_config:
            # Map our config to model provider parameters
            temperature = model_config.get('temperature', 0.7)
            max_tokens = model_config.get('max_tokens', 2048)
            
            resp = await local_model.chat(
                [m.dict() if isinstance(m, BaseModel) else m for m in req.messages],
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            # Use defaults
            resp = await local_model.chat(
                [m.dict() if isinstance(m, BaseModel) else m for m in req.messages],
                temperature=0.7,
                max_tokens=2048
            )
        
        return {"response": resp, "model": model_to_use}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local model error: {str(e)}")


# ============================================================
# Wikipedia API Endpoints
# ============================================================

@app.get("/api/wiki/song/{title}")
async def get_wiki_song(title: str, artist: Optional[str] = None):
    """
    Get song information from Wikipedia
    
    Query params:
        artist: Artist name (optional but recommended for disambiguation)
    """
    try:
        song_info = await wikipedia_service.get_song_info(title, artist)
        if not song_info:
            raise HTTPException(status_code=404, detail="Song not found on Wikipedia")
        return song_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wikipedia error: {str(e)}")


@app.get("/api/wiki/artist/{artist_name}")
async def get_wiki_artist(artist_name: str):
    """Get artist information from Wikipedia"""
    try:
        artist_info = await wikipedia_service.get_artist_info(artist_name)
        if not artist_info:
            raise HTTPException(status_code=404, detail="Artist not found on Wikipedia")
        return artist_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wikipedia error: {str(e)}")


@app.get("/api/wiki/album/{album_title}")
async def get_wiki_album(album_title: str, artist: Optional[str] = None):
    """
    Get album information from Wikipedia
    
    Query params:
        artist: Artist name (optional but recommended for disambiguation)
    """
    try:
        album_info = await wikipedia_service.get_album_info(album_title, artist)
        if not album_info:
            raise HTTPException(status_code=404, detail="Album not found on Wikipedia")
        return album_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wikipedia error: {str(e)}")


@app.get("/api/wiki/search")
async def search_wiki(q: str):
    """
    Search Wikipedia
    
    Query params:
        q: Search query
    """
    try:
        results = await wikipedia_service.search_wikipedia(q)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wikipedia search error: {str(e)}")


# ============================================================
# MusicBrainz API Endpoints
# ============================================================

@app.get("/api/mb/artist/{artist_name}")
async def search_mb_artist(artist_name: str):
    """Search for artist on MusicBrainz"""
    try:
        artist = await musicbrainz_service.mb_search_artist_by_name(artist_name)
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found on MusicBrainz")
        return artist
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MusicBrainz error: {str(e)}")


@app.get("/api/mb/recording")
async def search_mb_recording(title: str, artist: str):
    """
    Search for recording (track) on MusicBrainz
    
    Query params:
        title: Track title
        artist: Artist name
    """
    try:
        recording = await musicbrainz_service.mb_search_recording(title, artist)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found on MusicBrainz")
        return recording
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MusicBrainz error: {str(e)}")


@app.get("/api/mb/artist/{artist_id}/genres")
async def get_mb_artist_genres(artist_id: str):
    """Get artist genres and tags from MusicBrainz"""
    try:
        genres_tags = await musicbrainz_service.mb_artist_genres_tags(artist_id)
        return genres_tags
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MusicBrainz error: {str(e)}")


@app.get("/api/mb/artist/{artist_id}/discography")
async def get_mb_artist_discography(artist_id: str, limit: int = 100):
    """
    Get artist discography from MusicBrainz (filtered for albums)
    
    Query params:
        limit: Maximum number of results (default 100)
    """
    try:
        release_groups = await musicbrainz_service.mb_release_groups_filtered_by_artist(artist_id, limit)
        summary = musicbrainz_service.summarize_discography(release_groups)
        return {
            "releaseGroups": release_groups,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MusicBrainz error: {str(e)}")


# ============================================================
# WebSocket Room Handler
# ============================================================

@app.websocket("/ws/room")
async def websocket_room(websocket: WebSocket):
    """
    WebSocket endpoint for room events
    
    Receives events from hang-bot and sends commands back
    """
    await websocket_room_endpoint(websocket)


# ============================================================
# Phase 1: Model Management, Logging, and Services
# ============================================================

if PHASE_1_ENABLED:
    # Pydantic models for new endpoints
    class DownloadModelRequest(BaseModel):
        model_id: str
    
    class ModelConfigUpdate(BaseModel):
        temperature: Optional[float] = None
        max_tokens: Optional[int] = None
        response_style: Optional[int] = None
        creativity: Optional[int] = None
        context_window: Optional[int] = None
    
    class HuggingFaceTokenRequest(BaseModel):
        token: str
    
    # Model Management Endpoints
    @app.get("/api/models/available")
    async def list_available_models():
        """List all available models from the registry"""
        try:
            models = model_manager.get_available_models()
            return {"success": True, "models": models}
        except Exception as e:
            log_error(f"Error listing available models: {e}", category="model")
            raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")
    
    @app.get("/api/models/installed")
    async def list_installed_models():
        """List all installed models"""
        try:
            models = model_manager.get_installed_models()
            return {"success": True, "models": models}
        except Exception as e:
            log_error(f"Error listing installed models: {e}", category="model")
            raise HTTPException(status_code=500, detail=f"Error listing installed models: {str(e)}")
    
    @app.post("/api/models/download")
    async def download_model_endpoint(request: DownloadModelRequest, background_tasks: BackgroundTasks):
        """Start downloading a model in the background"""
        model_id = request.model_id
        
        # Check if model exists in registry
        model = model_manager.get_model_by_id(model_id)
        if not model:
            log_error(f"Model {model_id} not found in registry", category="model")
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Check if model is already being downloaded
        download_progress = model_manager.get_download_progress(model_id)
        if download_progress and download_progress["status"] == "downloading":
            return {"success": True, "status": "already_downloading", "progress": download_progress}
        
        # Check if model is already installed
        if model.get("installed", False):
            return {"success": True, "status": "already_installed", "model": model}
        
        # Start the download in a background task
        log_info(f"Starting download of model {model['name']}", category="model")
        background_tasks.add_task(model_manager.download_model, model_id)
        
        return {
            "success": True, 
            "status": "download_started", 
            "model_id": model_id,
            "message": f"Download started for {model['name']}. Monitor progress at /api/models/progress/{model_id}"
        }
    
    @app.get("/api/models/progress/{model_id}")
    async def get_model_download_progress(model_id: str):
        """Get the current progress of a model download"""
        progress = model_manager.get_download_progress(model_id)
        if not progress:
            # Check if model is already installed
            model = model_manager.get_model_by_id(model_id)
            if model and model.get("installed", False):
                return {"success": True, "status": "completed", "model_id": model_id, "progress_percent": 100}
            else:
                return {"success": False, "error": f"No active download for model {model_id}"}
        
        return {"success": True, "progress": progress}
    
    @app.delete("/api/models/delete/{model_id}")
    async def delete_model_endpoint(model_id: str):
        """Delete a downloaded model"""
        # Check if model exists
        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Check if model is being downloaded
        download_progress = model_manager.get_download_progress(model_id)
        if download_progress and download_progress["status"] == "downloading":
            raise HTTPException(status_code=409, detail=f"Cannot delete model that is currently downloading")
        
        # Delete the model
        result = model_manager.delete_model(model_id)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
    
    @app.get("/api/models/config/{model_id}")
    async def get_model_config_endpoint(model_id: str):
        """Get the configuration for a model"""
        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        config = model_manager.get_model_config(model_id)
        if not config:
            return {"success": False, "error": "No configuration found for this model"}
        
        return {"success": True, "config": config}
    
    @app.post("/api/models/config/{model_id}")
    async def update_model_config_endpoint(model_id: str, config_update: ModelConfigUpdate):
        """Update the configuration for a model"""
        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Get existing config or create default
        config = model_manager.get_model_config(model_id)
        if not config:
            # Create default config
            model_manager._create_default_config(model_id)
            config = model_manager.get_model_config(model_id)
            if not config:
                raise HTTPException(status_code=500, detail="Failed to create configuration")
        
        # Update config with new values
        update_dict = config_update.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                config[key] = value
        
        # Save updated config
        success = model_manager.save_model_config(model_id, config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
        return {"success": True, "config": config}
    
    # Model Loading Progress Endpoint (in-memory loading status)
    @app.get("/api/models/loading")
    async def get_models_loading_status():
        """
        Get current in-memory loading status for all models.
        This is separate from download progress - it tracks loading from disk to memory.
        """
        if not model_loader:
            return {"success": True, "loading_models": {}}
        try:
            return {"success": True, "loading_models": model_loader.get_all()}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # HuggingFace Token Management Endpoints
    @app.get("/api/auth/huggingface/status")
    async def get_hf_token_status():
        """Check if HuggingFace token is configured"""
        try:
            status = model_manager.get_hf_token_status()
            return {"success": True, **status}
        except Exception as e:
            log_error(f"Error checking HF token status: {e}", category="auth")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/auth/huggingface/token")
    async def save_hf_token(request: HuggingFaceTokenRequest):
        """Save HuggingFace authentication token"""
        try:
            result = model_manager.save_hf_token(request.token)
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error saving HF token: {e}", category="auth")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/auth/huggingface/token")
    async def clear_hf_token():
        """Clear stored HuggingFace token"""
        try:
            result = model_manager.clear_hf_token()
            if not result["success"]:
                raise HTTPException(status_code=500, detail=result["error"])
            return result
        except Exception as e:
            log_error(f"Error clearing HF token: {e}", category="auth")
            raise HTTPException(status_code=500, detail=str(e))
    
    # WebSocket endpoint for real-time download progress
    @app.websocket("/ws/models/progress/{model_id}")
    async def websocket_model_progress(websocket: WebSocket, model_id: str):
        await websocket.accept()
        
        model = model_manager.get_model_by_id(model_id)
        if not model:
            await websocket.send_json({"success": False, "error": f"Model {model_id} not found"})
            await websocket.close()
            return
        
        try:
            # Send progress updates every second
            while True:
                progress = model_manager.get_download_progress(model_id)
                
                # If model is already installed or download completed/failed
                if not progress:
                    if model.get("installed", False):
                        await websocket.send_json({
                            "success": True, 
                            "status": "completed", 
                            "model_id": model_id,
                            "progress_percent": 100
                        })
                    break
                
                # Send progress update
                await websocket.send_json({
                    "success": True,
                    "model_id": model_id,
                    "status": progress["status"],
                    "downloaded_bytes": progress["downloaded_bytes"],
                    "total_bytes": progress["total_bytes"],
                    "progress_percent": progress["progress_percent"],
                    "error": progress["error"],
                    "elapsed_seconds": progress["elapsed_seconds"]
                })
                
                # If download completed or failed, exit
                if progress["status"] in ["completed", "failed"]:
                    break
                    
                # Wait before next update
                await asyncio.sleep(1)
                
        except WebSocketDisconnect:
            log_info(f"WebSocket disconnected for model {model_id}", category="model")
        except Exception as e:
            log_error(f"Error in WebSocket for model {model_id}: {e}", category="model")
        finally:
            try:
                await websocket.close()
            except:
                pass
    
    # Logging Endpoints
    @app.get("/api/logs/level")
    async def get_log_level():
        """Get the current log level"""
        return {"level": get_current_log_level(), "levels": get_log_levels()}
    
    @app.post("/api/logs/level")
    async def set_log_level_endpoint(request: Dict[str, str]):
        """Set the log level"""
        level = request.get("level", "INFO")
        success = set_log_level(level)
        if not success:
            raise HTTPException(status_code=400, detail=f"Invalid log level: {level}")
        return {"success": True, "level": get_current_log_level()}
    
    @app.get("/api/logs/api_calls")
    async def get_api_calls(limit: int = 20):
        """Get recent API calls that would appear in chat"""
        return {"calls": api_call_logger.get_recent_calls(limit)}
    
    # Service Status Endpoint
    @app.get("/api/services/status")
    async def get_services_status():
        """Get the status of all services"""
        return service_manager.get_status()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
