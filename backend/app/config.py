"""Application settings, read from environment variables or a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "DineSense AI"
    api_prefix: str = "/api"
    debug: bool = True

    # Postgres in Docker / production. Falls back to a local SQLite file so the
    # API runs with no database server installed - useful while developing.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'dinesense.db'}"

    # JWT. CHANGE secret_key BEFORE DEPLOYING - anyone holding it can mint a
    # token for any account. Generate one with:
    #     python -c "import secrets; print(secrets.token_urlsafe(48))"
    # Must be at least 32 bytes for HS256 (RFC 7518).
    secret_key: str = "dev-only-secret-not-for-deployment-change-me-now"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # Where the trained models live
    ml_dir: Path = PROJECT_ROOT / "ml"

    # Frontend origins allowed to call this API
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # Batch upload guard rail
    max_batch_rows: int = 5_000

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def secret_is_default(self) -> bool:
        return self.secret_key.startswith("dev-only-secret")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
