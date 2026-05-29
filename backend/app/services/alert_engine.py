"""
Alert evaluation engine — polls every 60 seconds during IST market hours.
Evaluates all active alerts against live prices; triggers matching ones
and broadcasts via Redis pub/sub → WebSocket → frontend.
"""
import asyncio
import json
from datetime import datetime, timezone
import structlog
import asyncpg
import redis.asyncio as aioredis

from app.db import get_connection
from app.redis_client import get_redis
from app.queries.alerts import get_active_alerts, trigger_alert
from app.services.price_service import get_bulk_prices
from app.services.ws_manager import make_event

log = structlog.get_logger()


def _is_market_hours() -> bool:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    t = now.hour * 60 + now.minute
    return 555 <= t <= 930  # 9:15 to 15:30


async def evaluate_alerts():
    """Single evaluation pass — called every 60s by the engine loop."""
    redis = get_redis()
    async with get_connection() as conn:
        alerts = await get_active_alerts(conn)
        if not alerts:
            return

        symbols = list({a["symbol"] for a in alerts})
        prices = await get_bulk_prices(symbols, redis)

        for alert in alerts:
            sym = alert["symbol"]
            price = prices.get(sym)
            if price is None:
                continue
            if _condition_met(alert, price):
                await trigger_alert(conn, alert["id"], price)
                event = make_event("alert.triggered", {
                    "alert_id": str(alert["id"]),
                    "symbol": sym,
                    "alert_type": alert["alert_type"],
                    "message": alert["message"] or _default_message(alert, price),
                    "price": price,
                    "severity": "warning",
                })
                await redis.publish("alert:triggered", json.dumps(event))
                log.info("alert_triggered", symbol=sym, alert_type=alert["alert_type"], price=price)


def _condition_met(alert: asyncpg.Record, price: float) -> bool:
    t = alert["alert_type"]
    threshold = alert["threshold_value"]
    match t:
        case "price_above":    return threshold is not None and price >= threshold
        case "price_below":    return threshold is not None and price <= threshold
        case "volume_spike":   return False  # handled separately via scan results
        case _:                return False


def _default_message(alert: asyncpg.Record, price: float) -> str:
    t = alert["alert_type"]
    sym = alert["symbol"]
    threshold = alert["threshold_value"]
    if t == "price_above":
        return f"{sym} crossed above ₹{threshold:.2f} (current: ₹{price:.2f})"
    if t == "price_below":
        return f"{sym} fell below ₹{threshold:.2f} (current: ₹{price:.2f})"
    return f"{sym} alert triggered at ₹{price:.2f}"


class AlertEngine:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("alert_engine_started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("alert_engine_stopped")

    async def _loop(self):
        while self._running:
            if _is_market_hours():
                try:
                    await evaluate_alerts()
                except Exception as e:
                    log.error("alert_engine_error", error=str(e))
            await asyncio.sleep(60)


alert_engine = AlertEngine()
