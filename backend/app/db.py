import asyncpg
import structlog
from app.config import get_settings

log = structlog.get_logger()

_pool: asyncpg.Pool | None = None
_read_pool: asyncpg.Pool | None = None  # NeonDB read-replica pool (optional)


async def create_pool() -> asyncpg.Pool:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=20,
        command_timeout=30,
        statement_cache_size=200,
        # Proactively replace connections idle >4 min so NeonDB's 5-min
        # idle timeout never surprises us mid-request.
        max_inactive_connection_lifetime=240,
    )
    log.info("db_pool_created", min=2, max=20)

    # Optionally create a read-replica pool if READ_REPLICA_URL is configured
    if settings.read_replica_url:
        await create_read_pool(settings.read_replica_url)

    return _pool


async def create_read_pool(dsn: str) -> asyncpg.Pool:
    """Create a separate pool pointing at the NeonDB read replica."""
    global _read_pool
    _read_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=10,
        command_timeout=30,
        statement_cache_size=200,
        max_inactive_connection_lifetime=240,
    )
    log.info("db_read_pool_created", min=1, max=10)
    return _read_pool


async def close_pool():
    global _pool, _read_pool
    if _pool:
        await _pool.close()
        _pool = None
    if _read_pool:
        await _read_pool.close()
        _read_pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call create_pool() at startup")
    return _pool


def get_read_pool() -> asyncpg.Pool:
    """Return the read-replica pool if configured, else fall back to primary."""
    return _read_pool if _read_pool is not None else get_pool()


class _ConnCtx:
    """Async context manager that acquires a connection from the given pool."""
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def __aenter__(self) -> asyncpg.Connection:
        self._conn = await self._pool.acquire()
        return self._conn

    async def __aexit__(self, *_):
        await self._pool.release(self._conn)


def get_connection() -> _ConnCtx:
    return _ConnCtx(get_pool())


def get_read_connection() -> _ConnCtx:
    """Acquire a connection from the read replica (falls back to primary)."""
    return _ConnCtx(get_read_pool())
