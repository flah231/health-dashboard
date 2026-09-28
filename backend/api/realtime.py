"""WebSocket 端点 + 内部通知接口。"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ws_manager import manager

log = logging.getLogger("realtime")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # 保持连接，收到客户端消息（心跳）就回一个 pong
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception as e:
        log.warning(f"WebSocket 异常：{e}")
        await manager.disconnect(ws)


@router.post("/notify")
async def notify(payload: dict | None = None):
    """供采集器调用：数据已更新，让所有前端刷新。"""
    count = await manager.broadcast({
        "type": "data_updated",
        "source_key": (payload or {}).get("source_key"),
        "record_count": (payload or {}).get("record_count"),
    })
    return {"ok": True, "broadcast_to": count}