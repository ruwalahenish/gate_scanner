import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import create_pool, close_pool
from app.limiter import limiter
from app.metrics import setup_metrics
from app.redis_client import create_redis, close_redis
from app.exceptions import GATEBaseError
from app.services.ws_manager import manager
from app.routers import (
    signals, paper_trading, scans, dashboard,
    universe, market, backtests, stock_master, internal,
)

# Structured logging — pretty console in dev; swap ConsoleRenderer for JSONRenderer in prod
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    log.info("startup_begin")
    await create_pool()
    redis = await create_redis()
    redis_listener_task = asyncio.create_task(manager.listen_redis(redis))
    log.info("startup_complete")

    yield  # ← application runs here

    # ── Shutdown ─────────────────────────────────────────────────────
    # Cancel the Redis pub/sub listener before closing Redis so it doesn't
    # raise ConnectionError ("Connection closed by server.") on shutdown.
    redis_listener_task.cancel()
    try:
        await redis_listener_task
    except asyncio.CancelledError:
        pass

    await close_pool()
    await close_redis()
    from app.services.scan_service import _executor as scan_executor
    from app.services.price_service import _executor as price_executor
    from app.services.stock_service import _executor as stock_executor
    scan_executor.shutdown(wait=False)
    price_executor.shutdown(wait=False)
    stock_executor.shutdown(wait=False)
    log.info("shutdown_complete")


app = FastAPI(
    title="GATE Trading Intelligence API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus metrics at /metrics (excluded from docs)
setup_metrics(app)

# Middleware stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request-ID middleware — stamps every request for log correlation / tracing
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Global error handler for domain exceptions
@app.exception_handler(GATEBaseError)
async def gate_error_handler(_request: Request, exc: GATEBaseError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Health check
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "gate-trading-api", "version": "1.0.0"}


@app.get("/api/health/detailed")
async def health_detailed():
    """Extended health — DB pool stats, Redis ping, last scan info."""
    from app.db import get_pool
    from app.redis_client import get_redis

    result: dict = {"db_ok": False, "redis_ok": False}

    # ── DB pool ────────────────────────────────────────────────────────
    try:
        pool = get_pool()
        result["db_ok"] = True
        result["db_pool_size"] = pool.get_size()
        result["db_pool_idle"] = pool.get_idle_size()
    except Exception as exc:
        result["db_error"] = str(exc)

    # ── Redis ──────────────────────────────────────────────────────────
    try:
        redis = get_redis()
        await redis.ping()
        result["redis_ok"] = True
    except Exception as exc:
        result["redis_error"] = str(exc)

    # ── Last scan ──────────────────────────────────────────────────────
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT triggered_at, completed_at, duration_sec, signals_found "
                "FROM scans WHERE status='done' ORDER BY triggered_at DESC LIMIT 1"
            )
        if row:
            result["last_scan_at"] = row["triggered_at"].isoformat() if row["triggered_at"] else None
            result["last_scan_completed_at"] = row["completed_at"].isoformat() if row["completed_at"] else None
            result["last_scan_duration_sec"] = float(row["duration_sec"]) if row["duration_sec"] else None
            result["last_scan_signals"] = row["signals_found"]
        else:
            result["last_scan_at"] = None
    except Exception:
        result["last_scan_at"] = None

    return result


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await manager.disconnect(ws)


# Internal task-trigger endpoints — called by cron-job.org (replaces Celery Beat)
app.include_router(internal.router, prefix="/api/internal")

# Mount routers — both /api/ (legacy) and /api/v1/ (versioned, forward-compatible)
for prefix in ("/api", "/api/v1"):
    app.include_router(dashboard.router,      prefix=f"{prefix}/dashboard")
    app.include_router(scans.router,          prefix=f"{prefix}/scans")
    app.include_router(signals.router,        prefix=f"{prefix}/signals")   # legacy; unmounted in M5
    app.include_router(paper_trading.router,  prefix=f"{prefix}/paper-trading")
    app.include_router(universe.router,       prefix=f"{prefix}/universe")
    app.include_router(market.router,         prefix=f"{prefix}/market")
    app.include_router(backtests.router,      prefix=f"{prefix}/backtests")
    app.include_router(stock_master.router,   prefix=f"{prefix}/stocks")
