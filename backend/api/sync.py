"""同步触发接口。"""
import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ws_manager import manager

log = logging.getLogger("sync")
router = APIRouter()

STATE = {
    "running": False,
    "current_source": None,
    "current_index": 0,
    "total_sources": 0,
    "done_sources": [],
    "pending_sources": [],
    "total_records": 0,
}
_current_process: subprocess.Popen | None = None
_last_trigger_time: float = 0.0
_DEBOUNCE_SECONDS = 5.0    # 5 秒内不允许重复触发


class ProgressBody(BaseModel):
    source_key: str
    index: int = 0
    total_sources: int = 0
    record_count: int = 0


class SourceDoneBody(BaseModel):
    source_key: str
    record_count: int
    skipped: bool = False


class StartBody(BaseModel):
    sources: list[str]


class FinishBody(BaseModel):
    total_records: int


@router.get("/sync/status")
def sync_status():
    return STATE


def _find_run_sync():
    """查找 run_sync（优先 exe，其次 py）。返回 (type, path, cwd)。"""
    # 打包模式：backend.exe 在 <resources>/backend/，run_sync.exe 在 <resources>/collector/
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent    # .../resources/backend
        resources_dir = exe_dir.parent                     # .../resources

        # 优先 run_sync.exe
        exe_path = resources_dir / "collector" / "run_sync.exe"
        if exe_path.exists():
            return ("exe", exe_path, exe_path.parent)

        # 回退 run_sync.py
        py_path = resources_dir / "collector" / "run_sync.py"
        if py_path.exists():
            return ("py", py_path, py_path.parent)

    # 开发模式
    backend_dir = Path(__file__).resolve().parent.parent      # .../backend
    project_root = backend_dir.parent                          # .../health-dashboard
    py_path = project_root / "collector" / "run_sync.py"
    if py_path.exists():
        return ("py", py_path, py_path.parent)

    return (None, None, None)


@router.post("/sync/smart")
async def sync_smart(skip_hours: int = Query(24)):
    global _current_process

    if STATE["running"]:
        return {"ok": False, "message": "同步已在进行中"}

    runner_type, runner_path, cwd = _find_run_sync()
    if runner_type is None:
        return {"ok": False, "message": "找不到 run_sync.exe 或 run_sync.py"}

    log.info(f"[Sync] runner={runner_type} path={runner_path}")

    # 环境变量：传数据目录给 run_sync
    child_env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
    }
    # 打包模式下，父进程已经设了 HEALTH_APP_DIR 等，自动继承
    # 如果没有，从默认位置补上
    if "HEALTH_APP_DIR" not in child_env:
        appdata = os.getenv("APPDATA") or os.path.expanduser("~")
        app_dir = Path(appdata) / "HealthDashboard"
        app_dir.mkdir(parents=True, exist_ok=True)
        child_env["HEALTH_APP_DIR"] = str(app_dir)
        child_env["HEALTH_LOG_DIR"] = str(app_dir / "logs")
        child_env["HEALTH_DB_PATH"] = str(app_dir / "health_dashboard.db")

    # 组装命令
    if runner_type == "exe":
        cmd = [str(runner_path), "--skip-hours", str(skip_hours)]
    else:
        cmd = [sys.executable, str(runner_path), "--skip-hours", str(skip_hours)]

    try:
        _current_process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=child_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.exception("启动 run_sync 失败")
        return {"ok": False, "message": f"启动失败：{e}"}

    log.info(f"[Sync] PID={_current_process.pid}")
    return {"ok": True, "message": "同步已启动", "pid": _current_process.pid}


@router.post("/sync/start")
async def sync_start(body: StartBody):
    STATE["running"] = True
    STATE["pending_sources"] = list(body.sources)
    STATE["done_sources"] = []
    STATE["current_source"] = None
    STATE["current_index"] = 0
    STATE["total_sources"] = len(body.sources)
    STATE["total_records"] = 0
    await manager.broadcast({"type": "sync_started", "sources": body.sources})
    return {"ok": True}


@router.post("/sync/progress")
async def sync_progress(body: ProgressBody):
    STATE["current_source"] = body.source_key
    await manager.broadcast({
        "type": "sync_progress",
        "source_key": body.source_key,
    })
    return {"ok": True}


@router.post("/sync/source_done")
async def sync_source_done(body: SourceDoneBody):
    if body.source_key in STATE["pending_sources"]:
        STATE["pending_sources"].remove(body.source_key)
    STATE["done_sources"].append(body.source_key)
    STATE["total_records"] += body.record_count
    await manager.broadcast({
        "type": "sync_source_done",
        "source_key": body.source_key,
        "record_count": body.record_count,
        "skipped": body.skipped,
    })
    return {"ok": True}


@router.post("/sync/finish")
async def sync_finish(body: FinishBody):
    STATE["running"] = False
    STATE["current_source"] = None
    await manager.broadcast({
        "type": "sync_finished",
        "total_records": body.total_records,
    })
    return {"ok": True}