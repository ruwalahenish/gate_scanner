"""Health check and basic smoke tests."""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.anyio
async def test_health_endpoint():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "version" in body


@pytest.mark.anyio
async def test_metrics_endpoint():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert b"gate_" in resp.content or b"http_" in resp.content
