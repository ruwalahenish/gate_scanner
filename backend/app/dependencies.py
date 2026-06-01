import asyncpg
import redis.asyncio as aioredis
from fastapi import Request
from app.db import get_pool
from app.redis_client import get_redis


async def db_conn(request: Request) -> asyncpg.Connection:
    """FastAPI dependency: yields an asyncpg connection from the pool.

    If the acquired connection is already closed (stale from Neon's pooler),
    we release it and acquire a fresh one.
    """
    pool = get_pool()
    conn = await pool.acquire()
    # Guard against stale connections returned by the pool
    if conn.is_closed():
        await pool.release(conn)
        conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


async def redis_client(request: Request) -> aioredis.Redis:
    """FastAPI dependency: returns the shared Redis client."""
    return get_redis()
