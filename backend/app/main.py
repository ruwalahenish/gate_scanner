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
from app.services.alert_engine import alert_engine
from app.routers import (
    signals, portfolio, alerts, scans,
    universe, watchlist, market, backtests, stock_master,
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
    asyncio.create_task(manager.listen_redis(redis))
    await alert_engine.start()
    log.info("startup_complete")

    yield  # ← application runs here

    # ── Shutdown ─────────────────────────────────────────────────────
    await alert_engine.stop()
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


# Mount routers — both /api/ (legacy) and /api/v1/ (versioned, forward-compatible)
for prefix in ("/api", "/api/v1"):
    app.include_router(scans.router,        prefix=f"{prefix}/scans")
    app.include_router(signals.router,      prefix=f"{prefix}/signals")
    app.include_router(portfolio.router,    prefix=f"{prefix}/portfolio")
    app.include_router(alerts.router,       prefix=f"{prefix}/alerts")
    app.include_router(universe.router,     prefix=f"{prefix}/universe")
    app.include_router(watchlist.router,    prefix=f"{prefix}/watchlist")
    app.include_router(market.router,       prefix=f"{prefix}/market")
    app.include_router(backtests.router,    prefix=f"{prefix}/backtests")
    app.include_router(stock_master.router, prefix=f"{prefix}/stocks")
