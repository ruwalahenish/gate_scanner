"""
Integration tests for key FastAPI routers.
DB and Redis are mocked — no external services needed.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


def _make_app_client(mock_db_conn, mock_redis):
    from app.main import app
    from app.dependencies import db_conn, redis_client
    app.dependency_overrides[db_conn] = lambda: mock_db_conn
    app.dependency_overrides[redis_client] = lambda: mock_redis
    return app


@pytest.mark.anyio
async def test_get_scans_returns_list():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    redis = AsyncMock()

    app = _make_app_client(conn, redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/scans")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_trigger_scan_returns_scan_id():
    import uuid
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)

    with patch("app.routers.scans.has_running_scan", return_value=False), \
         patch("app.routers.scans.create_scan", return_value=None), \
         patch("app.routers.scans.run_scan_task") as mock_task:
        mock_task.apply_async = AsyncMock()
        app = _make_app_client(conn, redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/scans/trigger", json={"mode": "daily", "universe": []})

    assert resp.status_code == 200
    assert "scan_id" in resp.json()
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_signals_returns_list():
    conn = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # cache miss
    redis.set = AsyncMock(return_value=True)

    with patch("app.routers.signals.get_latest_signals", return_value=([], 0)):
        app = _make_app_client(conn, redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/signals")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_portfolio_summary_returns_dict():
    conn = AsyncMock()
    redis = AsyncMock()

    summary = {
        "initial_capital": 1000000.0,
        "current_capital": 950000.0,
        "invested_value": 50000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "total_pnl": 0.0,
        "total_pnl_pct": 0.0,
        "open_positions": 0,
        "total_trades": 0,
        "winning_trades": 0,
        "win_rate": 0.0,
    }

    with patch("app.routers.portfolio.q.get_portfolio_summary", return_value=summary), \
         patch("app.routers.portfolio.q.get_open_positions", return_value=[]):
        app = _make_app_client(conn, redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/portfolio/summary")

    assert resp.status_code == 200
    assert "current_capital" in resp.json()
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_rate_limit_scan_trigger():
    """Scan trigger should 429 after 5 requests/minute from same IP."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)

    with patch("app.routers.scans.has_running_scan", return_value=False), \
         patch("app.routers.scans.create_scan", return_value=None), \
         patch("app.routers.scans.run_scan_task") as mock_task:
        mock_task.apply_async = AsyncMock()
        app = _make_app_client(conn, redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            responses = [
                await c.post("/api/scans/trigger", json={"mode": "daily", "universe": []})
                for _ in range(7)
            ]

    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "Expected rate limit 429 after 5 requests"
    app.dependency_overrides.clear()
