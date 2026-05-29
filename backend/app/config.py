from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

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

    # Telegram (optional — leave empty to disable)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Gate cache dir (reuses existing cache)
    gate_cache_dir: str = "../.gate_cache"

    # Scan concurrency
    scan_executor_workers: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
