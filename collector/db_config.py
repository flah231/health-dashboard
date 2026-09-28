"""统一数据库路径配置（支持 PyInstaller 打包）。"""
import os
import sys
from pathlib import Path


def _is_packaged() -> bool:
    """是否在 PyInstaller 打包的 exe 里运行。"""
    return getattr(sys, 'frozen', False)


def get_app_data_dir() -> Path:
    """应用数据目录（数据库、日志、缓存都放这里）。

    优先级：
        1. 环境变量 HEALTH_APP_DIR
        2. Windows: %APPDATA%/HealthDashboard
        3. 其他: ~/.health-dashboard
    """
    env_dir = os.getenv("HEALTH_APP_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    if sys.platform == "win32":
        appdata = os.getenv("APPDATA") or str(Path.home())
        p = Path(appdata) / "HealthDashboard"
    else:
        p = Path.home() / ".health-dashboard"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_path() -> Path:
    """数据库文件路径。"""
    return get_app_data_dir() / "health_dashboard.db"


def get_log_dir() -> Path:
    """日志目录。"""
    p = get_app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


DB_PATH = get_db_path()
LOG_DIR = get_log_dir()