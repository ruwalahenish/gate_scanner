"""
WebSocket connection registry with Redis Pub/Sub broadcast.

Designed to be Centrifugo-compatible: the broadcast() and publish()
interface is identical whether messages are delivered via in-process
fan-out (current) or via an external Centrifugo hub (future).
Switching to Centrifugo only requires replacing listen_redis() with
a thin Centrifugo publisher and removing the in-process registry.
"""
import asyncio
import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from fastapi import WebSocket
import structlog

from app.core.json_utils import CustomEncoder
from app.metrics import ws_connections

log = structlog.get_logger()

CHANNELS = [
    "scan:progress",
    "scan:complete",
    "scan:batch",
    "scan:post_process",
    "price:update",
]


class WebSocketManager:
    """
    In-process WebSocket hub backed by Redis pub/sub.

    To migrate to Centrifugo:
      1. Remove _connections, _lock, connect(), disconnect(), broadcast()
      2. In listen_redis(), publish each message to Centrifugo instead of
         calling self.broadcast()
      3. Connect clients to Centrifugo's WebSocket endpoint directly
    """

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        ws_connections.inc()
        log.info("ws_connected", total=len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
        ws_connections.dec()
        log.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, message: dict):
        if not self._connections:
            return
        try:
            data = json.dumps(message, cls=CustomEncoder)
        except Exception as e:
            log.warning("ws_serialize_error", error=str(e))
            return

        dead: set[WebSocket] = set()
        async with self._lock:
            snapshot = list(self._connections)

        for ws in snapshot:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead
            ws_connections.dec(len(dead))

    async def listen_redis(self, redis: aioredis.Redis):
        """Subscribe to all platform Redis channels and broadcast to WS clients."""
        pubsub = redis.pubsub()
        await pubsub.subscribe(*CHANNELS)
        log.info("ws_redis_listener_started", channels=CHANNELS)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                        await self.broadcast(payload)
                    except (json.JSONDecodeError, Exception) as e:
                        log.warning("ws_broadcast_error", error=str(e))
        except asyncio.CancelledError:
            await pubsub.unsubscribe(*CHANNELS)
            log.info("ws_redis_listener_stopped")


# Singleton — imported by main.py and routers
manager = WebSocketManager()


def make_event(event_type: str, payload: dict) -> dict:
    return {
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
