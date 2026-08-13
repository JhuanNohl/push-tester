import asyncio
from collections import deque
from datetime import datetime
from typing import Any

from fastapi import WebSocket


class Hub:
    """Log em memória do tráfego recebido + broadcast para os clientes WebSocket
    conectados na tela de monitoramento."""

    def __init__(self, max_history: int = 500) -> None:
        self._connections: set[WebSocket] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
            history = list(self._history)
        for event in history:
            await ws.send_json(event)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def emit(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
        self._history.append(event)
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)


hub = Hub()
