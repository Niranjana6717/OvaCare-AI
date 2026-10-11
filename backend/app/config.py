"""
Central application configuration.

All values are read from environment variables (see .env.example). Nothing
sensitive is hard-coded here. This module intentionally fails loudly if a
required secret is missing in a non-development environment, rather than
falling back to an insecure default.
"""
from __future__ import annotations

import secrets
import warnings
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Environment ---
    ENVIRONMENT: str = "development"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./ovacare_dev.db"
    DATABASE_URL_TEST: str = "sqlite:///./test.db"

    # --- Auth / JWT ---
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- API ---
    API_BASE_URL: str = "http://localhost:8000"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # --- ML ---
    MODEL_PATH: str = "./ml-platform/models/production"
    MODEL_REGISTRY_PATH: str = "./ml-platform/models"

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Admin bootstrap (optional) ---
    # Read only by scripts/bootstrap_admin.py, never by the running API
    # process itself — there is deliberately no HTTP endpoint that grants
    # the admin role (requirement #30: role elevation is an operational
    # action, not a self-service one). Leave both blank to skip bootstrap.
    ADMIN_BOOTSTRAP_EMAIL: str = ""
    ADMIN_BOOTSTRAP_PASSWORD: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if not settings.JWT_SECRET:
        if settings.is_production:
            raise RuntimeError(
                "JWT_SECRET must be set via environment variable in production. "
                "Refusing to start with an insecure default."
            )
        # Development-only fallback so `uvicorn` can boot without a .env file.
        # Never reachable in production because of the guard above.
        settings.JWT_SECRET = secrets.token_urlsafe(64)
        warnings.warn(
            "JWT_SECRET not set — generated an ephemeral development secret. "
            "All existing tokens will be invalidated on restart. Set JWT_SECRET "
            "in your .env file for a stable development session.",
            stacklevel=2,
        )

    return settings
