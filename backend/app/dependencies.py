import asyncpg
import redis.asyncio as aioredis
from fastapi import Request
from app.db import get_pool
from app.redis_client import get_redis


async def db_conn(request: Request) -> asyncpg.Connection:
    """FastAPI dependency: yields an asyncpg connection from the pool."""
    async with get_pool().acquire() as conn:
        yield conn


async def redis_client(request: Request) -> aioredis.Redis:
    """FastAPI dependency: returns the shared Redis client."""
    return get_redis()
