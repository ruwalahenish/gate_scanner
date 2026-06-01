import asyncio
import json
import logging

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import create_pool, close_pool
from app.redis_client import create_redis, close_redis
from app.exceptions import GATEBaseError
from app.services.ws_manager import manager
from app.services.alert_engine import alert_engine
from app.routers import signals, portfolio, alerts, scans, universe, watchlist, market, backtests, stock_master

# Structured logging setup
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

app = FastAPI(
    title="GATE Trading Intelligence API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Startup / shutdown
@app.on_event("startup")
async def startup():
    log.info("startup_begin")
    db_pool = await create_pool()
    redis = await create_redis()
    # Start Redis → WebSocket listener in background
    asyncio.create_task(manager.listen_redis(redis))
    # Start alert evaluation engine
    await alert_engine.start()
    log.info("startup_complete")


@app.on_event("shutdown")
async def shutdown():
    await alert_engine.stop()
    await close_pool()
    await close_redis()
    # Cleanly release thread pools to avoid resource leaks during restarts
    from app.services.scan_service import _executor as scan_executor
    from app.services.price_service import _executor as price_executor
    from app.services.stock_service import _executor as stock_executor
    scan_executor.shutdown(wait=False)
    price_executor.shutdown(wait=False)
    stock_executor.shutdown(wait=False)
    log.info("shutdown_complete")


# Global error handler for domain exceptions
@app.exception_handler(GATEBaseError)
async def gate_error_handler(request, exc: GATEBaseError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Health check
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "gate-trading-api"}


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


# Mount routers
app.include_router(scans.router,     prefix="/api/scans")
app.include_router(signals.router,   prefix="/api/signals")
app.include_router(portfolio.router, prefix="/api/portfolio")
app.include_router(alerts.router,    prefix="/api/alerts")
app.include_router(universe.router,  prefix="/api/universe")
app.include_router(watchlist.router, prefix="/api/watchlist")
app.include_router(market.router,    prefix="/api/market")
app.include_router(backtests.router,     prefix="/api/backtests")
app.include_router(stock_master.router,  prefix="/api/stocks")
