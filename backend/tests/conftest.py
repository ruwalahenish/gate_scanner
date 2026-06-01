"""
Shared pytest fixtures for the GATE backend test suite.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db_conn():
    """Minimal asyncpg connection mock."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="OK")
    conn.executemany = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_redis():
    """Minimal aioredis mock."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.mget = AsyncMock(return_value=[])
    r.delete = AsyncMock(return_value=1)
    r.publish = AsyncMock(return_value=1)
    return r


@pytest.fixture
async def client(mock_db_conn, mock_redis):
    """FastAPI test client with DB and Redis dependencies overridden."""
    from app.main import app
    from app.dependencies import db_conn, redis_client

    app.dependency_overrides[db_conn] = lambda: mock_db_conn
    app.dependency_overrides[redis_client] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
