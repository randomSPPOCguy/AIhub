"""
Configuration for AI Hub
Load API keys from environment variables or .env file
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    
    # Bot API Key for authentication (optional - if set, API requires this key)
    # Use keys generated with jpnohub- prefix (see generate_api_key.py)
    # Example: jpnohub-kL8mN2pQ5rT9vW3xY7zA1bC4dE6fG0hI
    BOT_API_KEY: Optional[str] = None
    
    # Default models
    DEFAULT_GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
    DEFAULT_CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    
    # Local Phi-3 for music info processing
    USE_PHI3_FOR_INFO: bool = True
    # Comma-separated list of local Phi-3 model names available on this machine
    LOCAL_PHI3_MODELS: Optional[str] = "microsoft/Phi-3-mini-4k-instruct"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Centralized default personality (system prompt)
    # If set, the server will inject this as the first system message
    # when a chat request doesn't include any system message.
    DEFAULT_PERSONALITY: Optional[str] = None

    # Keyword detection for ingestion
    # Comma-separated list of words/phrases that trigger bot replies
    BOT_KEYWORDS: Optional[str] = "bot,b0t,@bot,ai"
    # Max number of turns to keep per conversation
    DEFAULT_HISTORY_LIMIT: int = 12
    
    # ONNX Runtime Configuration
    USE_ONNX: bool = False
    # Execution provider: cuda|cpu|tensorrt,cuda|cuda,cpu|cpu
    ONNX_EXECUTION_PROVIDER: str = "cuda"
    # Path to ONNX model directory (leave blank for no model)
    ONNX_MODEL_DIR: Optional[str] = None
    # Enable TensorRT execution provider (experimental)
    ONNX_ENABLE_TRT: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
