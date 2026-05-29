"""
WebSocket connection registry with Redis Pub/Sub broadcast.
All FastAPI workers subscribe to the same Redis channels so clients
connected to any worker receive all events.
"""
import asyncio
import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from fastapi import WebSocket
import structlog

log = structlog.get_logger()

CHANNELS = ["scan:progress", "scan:complete", "alert:triggered", "price:update"]


class WebSocketManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        log.info("ws_connected", total=len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
        log.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, message: dict):
        if not self._connections:
            return
        data = json.dumps(message)
        dead: set[WebSocket] = set()
        async with self._lock:
            snapshot = set(self._connections)
        for ws in snapshot:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._connections -= dead

    async def listen_redis(self, redis: aioredis.Redis):
        """Subscribe to all platform Redis channels and broadcast to WS clients."""
        pubsub = redis.pubsub()
        await pubsub.subscribe(*CHANNELS)
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


# Singleton — imported by main.py and routers
manager = WebSocketManager()


def make_event(event_type: str, payload: dict) -> dict:
    return {
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
