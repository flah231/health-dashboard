"""FastAPI 入口（兼容 PyInstaller console=False）。"""
import os
import sys
from pathlib import Path

# ===== PyInstaller 兼容：stdout/stderr 为 None 时重定向到日志文件 =====
if sys.stdout is None or sys.stderr is None:
    log_dir_str = os.getenv("HEALTH_LOG_DIR")
    if not log_dir_str:
        appdata = os.getenv("APPDATA") or os.path.expanduser("~")
        log_dir_str = str(Path(appdata) / "HealthDashboard" / "logs")
    log_dir = Path(log_dir_str)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_fp = open(log_dir / "backend.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_fp
    if sys.stderr is None:
        sys.stderr = log_fp

# ===== 数据库初始化 =====
from init_db import init_db
init_db()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api import stats, realtime, sync

app = FastAPI(title="医疗疾病信息数据分析看板 API", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats.router,    prefix="/api/stats", tags=["stats"])
app.include_router(realtime.router, prefix="/api",       tags=["realtime"])
app.include_router(sync.router,     prefix="/api",       tags=["sync"])

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.8.0"}


def _find_frontend_dist():
    """前端静态文件路径（开发 vs 打包）。"""
    candidates = []
    # PyInstaller 打包后：exe 同级的 frontend-dist
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "frontend-dist")
        candidates.append(exe_dir.parent / "frontend-dist")
    # 开发环境
    candidates.append(Path(__file__).parent.parent / "frontend" / "dist")

    for p in candidates:
        if p.exists():
            return p
    return None


FRONTEND_DIST = _find_frontend_dist()
if FRONTEND_DIST:
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return {"error": "not found"}, 404
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "frontend not built"}, 404


if __name__ == "__main__":
    import uvicorn
    # 开发环境支持热重载
    if os.getenv("DEV_RELOAD", "0") == "1":
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        # PyInstaller 打包后不能用 "main:app" 字符串（模块不在磁盘）
        # 直接传 app 对象
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")