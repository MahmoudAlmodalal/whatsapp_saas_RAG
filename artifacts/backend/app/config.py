"""
app/config.py
─────────────
Central configuration loaded from environment variables via pydantic-settings.
All service URLs are validated at startup — fail fast if misconfigured.
"""
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "WhatsApp AI SaaS"
    ENVIRONMENT: str = "development"   # development | staging | production
    DEBUG: bool = True
    SECRET_KEY: str

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str     # redis://host:port/db

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── Document Storage ─────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "s3"  # supabase | s3
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""

    # ── WhatsApp / Meta Cloud API ────────────────────────────────────────────
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # ── LLM / DeepSeek ───────────────────────────────────────────────────────
    DEEPSEEK_API_KEY: str = ""  # required for TASK-010 LLM Orchestrator

    # ── Langfuse Observability (TASK-014) ────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""   # pk-lf-... from https://cloud.langfuse.com
    LANGFUSE_SECRET_KEY: str = ""   # sk-lf-...
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"  # override for self-hosted

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()  # type: ignore[call-arg]
