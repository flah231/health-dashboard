# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for collector (run_sync)。"""

import os
from pathlib import Path

PROJECT_ROOT = Path(os.getcwd()).parent
COLLECTOR_DIR = PROJECT_ROOT / "collector"

a = Analysis(
    [str(COLLECTOR_DIR / "run_sync.py")],
    pathex=[str(COLLECTOR_DIR)],
    binaries=[],
    datas=[
        # 适配器全部带进去
        (str(COLLECTOR_DIR / "adapters" / "*.py"), "adapters"),
        # 目录文件
        (str(COLLECTOR_DIR / "diseases_catalog.py"), "."),
        # 数据库配置
        (str(COLLECTOR_DIR / "db_config.py"), "."),
        # 数据库初始化
        (str(COLLECTOR_DIR / "init_db.py"), "."),
    ],
    hiddenimports=[
        # 采集器依赖
        "httpx",
        "httpcore",
        "h11",
        "bs4",
        "lxml",
        "lxml.etree",
        "lxml._elementpath",
        "soupsieve",
        "docx",
        # pywin32（Word COM 转换 .doc）
        "win32com",
        "win32com.client",
        "pythoncom",
        "pywintypes",
        # 各适配器（PyInstaller 不会自动发现）
        "adapters.nhc_cn",
        "adapters.gd_province",
        "adapters.zj_province",
        "adapters.js_province",
        "adapters.sd_province",
        "adapters.base",
        # SQLite
        "sqlite3",
        # 数据库模块（保险项）
        "db_config",
        "db",
        "init_db",
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
    name="run_sync",
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