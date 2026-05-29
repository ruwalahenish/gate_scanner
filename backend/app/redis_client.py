import redis.asyncio as aioredis
from app.config import get_settings

_redis: aioredis.Redis | None = None


async def create_redis() -> aioredis.Redis:
    global _redis
    settings = get_settings()
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call create_redis() at startup")
    return _redis
