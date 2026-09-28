"""后端数据库连接（SQLite 版）。"""
import sqlite3
from contextlib import contextmanager

from db_config import DB_PATH


def _configure(conn: sqlite3.Connection):
    """连接级配置。"""
    conn.row_factory = sqlite3.Row
    # 开启外键约束
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL 模式：读写并发更好
    conn.execute("PRAGMA journal_mode = WAL")


def get_conn() -> sqlite3.Connection:
    """返回一个 SQLite 连接。

    注意：SQLite 连接不是线程安全的，每个线程用自己的连接。
    我们给每个请求新建连接（SQLite 打开很快）。
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    _configure(conn)
    return conn


@contextmanager
def get_cursor():
    """上下文管理器：自动提交/关闭。"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()