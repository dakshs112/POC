"""
Application configuration via pydantic-settings.

Reads all values from the .env file and provides type-validated,
centralized configuration accessible via dependency injection.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings parsed from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Sportmonks API ──────────────────────────────────────────────
    SPORTMONKS_API_KEY: str = "your_api_key_here"
    SPORTMONKS_BASE_URL: str = "https://api.sportmonks.com/v3/motorsport"

    # ── MongoDB ─────────────────────────────────────────────────────
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "f1_pipeline"

    # ── HTTP Client ─────────────────────────────────────────────────
    REQUEST_TIMEOUT: int = 30
    MAX_CONCURRENT_REQUESTS: int = 5
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_BASE_DELAY: float = 1.0

    # ── Logging ─────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance (FastAPI dependency)."""
    return Settings()
