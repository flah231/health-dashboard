"""WebSocket 连接管理器 + 全局广播。"""
import asyncio
import logging
from typing import Set

from fastapi import WebSocket

log = logging.getLogger("ws")


class WSManager:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)
        log.info(f"WebSocket 连接建立，当前连接数：{len(self.connections)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.connections.discard(ws)
        log.info(f"WebSocket 断开，当前连接数：{len(self.connections)}")

    async def broadcast(self, message: dict):
        """广播 JSON 消息给所有连接。自动清理断开的连接。"""
        if not self.connections:
            return 0
        dead = []
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)
        log.info(f"已广播给 {len(self.connections)} 个连接")
        return len(self.connections)


manager = WSManager()