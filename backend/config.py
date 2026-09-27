"""
backend/config.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Centralized, validated application settings. Loads from environment / .env
and exposes a single cached `get_settings()` accessor. Also resolves which
LLM provider (Groq or Gemini) is active based on which API key is present,
with Groq preferred when both are configured (lower latency, generous
free tier), and Gemini used as the automatic fallback.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"
    NONE = "none"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App identity ---
    APP_NAME: str = "OmniScale Enterprise Pro"
    APP_AUTHOR: str = "NIKHIL CHARY SRIRAMOJU"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="change-me-in-production-please")
    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://omniscale:omniscale@localhost:5432/omniscale"
    )

    # --- Redis / Celery ---
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # --- Auth ---
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- LLM providers (dynamic; whichever key is present wins) ---
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # --- Embeddings / RAG ---
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_INDEX_DIR: str = "./data/vector_index"

    # --- CNN ---
    CNN_WEIGHTS_DIR: str = "./data/cnn_weights"

    # --- Stripe ---
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID_PRO: Optional[str] = None
    STRIPE_PRICE_ID_ENTERPRISE: Optional[str] = None
    STRIPE_CONNECT_ENABLED: bool = False
    FRONTEND_SUCCESS_URL: str = "http://localhost:3000/billing/success"
    FRONTEND_CANCEL_URL: str = "http://localhost:3000/billing/cancel"

    # --- Observability ---
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = True

    # --- Rate limiting ---
    RATE_LIMIT_FREE_PER_MIN: int = 20
    RATE_LIMIT_PRO_PER_MIN: int = 120
    RATE_LIMIT_ENTERPRISE_PER_MIN: int = 600

    @model_validator(mode="after")
    def _derive_celery_urls(self) -> "Settings":
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        return self

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Managed Postgres providers (Render, Railway, Heroku-style) hand out
        a plain `postgresql://` or `postgres://` connection string. The async
        engine needs an explicit `+asyncpg` driver, so normalize it here once
        rather than requiring every deploy target to know that detail."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.DATABASE_URL = url
        return self

    @property
    def active_llm_provider(self) -> LLMProvider:
        """Groq is preferred for latency; Gemini is the automatic fallback."""
        if self.GROQ_API_KEY:
            return LLMProvider.GROQ
        if self.GEMINI_API_KEY:
            return LLMProvider.GEMINI
        return LLMProvider.NONE

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
