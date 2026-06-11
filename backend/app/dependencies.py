import asyncpg
import redis.asyncio as aioredis
from fastapi import Request
from app.db import get_pool, get_read_pool
from app.redis_client import get_redis


async def _acquire_from(pool: asyncpg.Pool):
    conn = await pool.acquire()
    # Guard against stale connections returned by the pool (Neon's pooler)
    if conn.is_closed():
        await pool.release(conn)
        conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


async def db_conn(request: Request) -> asyncpg.Connection:
    """FastAPI dependency: yields an asyncpg connection from the primary pool."""
    async for conn in _acquire_from(get_pool()):
        yield conn


async def db_read_conn(request: Request) -> asyncpg.Connection:
    """FastAPI dependency for read-only endpoints.

    Uses the READ_REPLICA_URL pool when configured, otherwise falls back to
    the primary pool. Never use this for endpoints that read-after-write —
    replica lag would return stale data.
    """
    async for conn in _acquire_from(get_read_pool()):
        yield conn


async def redis_client(request: Request) -> aioredis.Redis:
    """FastAPI dependency: returns the shared Redis client."""
    return get_redis()
