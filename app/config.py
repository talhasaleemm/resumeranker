"""
app/config.py — Application configuration via pydantic-settings.
All values loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me"

    # Security
    ENCRYPTION_KEY: str = ""
    BLIND_INDEX_KEY: str = ""

    # PostgreSQL
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "resumeranker"
    postgres_user: str = "resumeranker"
    postgres_password: str = "devpassword123"
    database_url: str = (
        "postgresql+asyncpg://resumeranker:devpassword123@db:5432/resumeranker"
    )

    # File uploads
    max_upload_size_mb: int = 10

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # spaCy
    spacy_model: str = "en_core_web_sm"

    # Matching weights (must sum to 1.0)
    tfidf_weight: float = 0.4
    bm25_weight: float = 0.4
    skill_weight: float = 0.2

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of instantiating Settings()."""
    return Settings()
