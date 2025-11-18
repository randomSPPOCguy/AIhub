"""Configuration management for enrichment service."""

import os
from typing import List
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from config.env if it exists
PROJECT_ROOT = Path(__file__).resolve().parents[1]
env_path = PROJECT_ROOT / "config.env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


class Config:
    """Configuration class with environment variable defaults."""

    # Server configuration
    ENRICH_PORT: int = int(os.getenv("ENRICH_PORT", "8001"))
    ENRICH_HOST: str = os.getenv("ENRICH_HOST", "0.0.0.0")

    # Provider flags
    ENRICH_WIKIPEDIA_ENABLED: bool = os.getenv("ENRICH_WIKIPEDIA_ENABLED", "true").lower() == "true"
    ENRICH_MUSICBRAINZ_ENABLED: bool = os.getenv("ENRICH_MUSICBRAINZ_ENABLED", "true").lower() == "true"

    # Cache configuration
    ENRICH_CACHE_TTL_SECS: int = int(os.getenv("ENRICH_CACHE_TTL_SECS", "300"))

    # Request configuration
    ENRICH_REQUEST_TIMEOUT_SECS: float = float(os.getenv("ENRICH_REQUEST_TIMEOUT_SECS", "2.0"))
    ENRICH_MAX_RETRIES: int = int(os.getenv("ENRICH_MAX_RETRIES", "2"))

    # Service version
    SERVICE_VERSION: str = "1.0"


# Global config instance
config = Config()

