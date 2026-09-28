# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for backend (FastAPI)。"""

import os
from pathlib import Path

PROJECT_ROOT = Path(os.getcwd()).parent
BACKEND_DIR = PROJECT_ROOT / "backend"

a = Analysis(
    [str(BACKEND_DIR / "main.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=[
        # 把 api 目录里的所有 .py 也带进去
        (str(BACKEND_DIR / "api" / "*.py"), "api"),
    ],
    hiddenimports=[
        # uvicorn 的隐式导入
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # FastAPI 依赖
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "starlette",
        "anyio",
        # 数据源
        "pymysql",
        "sqlite3",
        # WebSocket
        "websockets",
        # 其他
        "dotenv",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不显示黑窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)