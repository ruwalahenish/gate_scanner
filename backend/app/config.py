import json
from pathlib import Path
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Walk up: app/ → backend/ → project root
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    # Database (NeonDB free tier)
    database_url: str = "postgresql://user:pass@host/gate_platform"

    # Redis (Docker local or Upstash free tier)
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> object:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Telegram (optional — leave empty to disable)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Gate cache dir (reuses existing cache)
    gate_cache_dir: str = "../.gate_cache"

    # Scan concurrency
    scan_executor_workers: int = 4

    # Optional NeonDB read-replica URL (leave empty to fall back to primary)
    read_replica_url: str = ""

    # Secret token for internal task-trigger endpoints (POST /api/internal/tasks/*)
    # Set via INTERNAL_SECRET env var. Leave empty to disable internal endpoints.
    internal_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
