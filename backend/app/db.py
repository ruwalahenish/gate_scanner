import asyncpg
from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
        statement_cache_size=100,
        # Proactively replace connections idle longer than 4 min so NeonDB's
        # 5-minute idle timeout never surprises us during long Celery tasks.
        max_inactive_connection_lifetime=240,
    )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call create_pool() at startup")
    return _pool


class _ConnCtx:
    """Async context manager that acquires a connection from the pool."""
    async def __aenter__(self) -> asyncpg.Connection:
        self._conn = await get_pool().acquire()
        return self._conn

    async def __aexit__(self, *_):
        await get_pool().release(self._conn)


def get_connection() -> _ConnCtx:
    return _ConnCtx()
