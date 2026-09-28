"""初始化 SQLite 数据库：建表 + 注册数据源。

幂等：重复运行不会损坏已有数据。
"""
import logging
import sqlite3

from db_config import DB_PATH
from db import get_conn

log = logging.getLogger("init_db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key        TEXT    UNIQUE NOT NULL,
    display_name      TEXT    NOT NULL,
    adapter_class     TEXT    NOT NULL,
    config_json       TEXT,
    enabled           INTEGER DEFAULT 1,
    crawl_interval_seconds INTEGER DEFAULT 3600,
    last_crawl_at     TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disease_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key    TEXT    NOT NULL,
    disease_name  TEXT    NOT NULL,
    region        TEXT    NOT NULL,
    stat_date     TEXT    NOT NULL,
    confirmed     INTEGER DEFAULT 0,
    cured         INTEGER DEFAULT 0,
    deaths        INTEGER DEFAULT 0,
    extra_json    TEXT,
    crawl_time    TEXT DEFAULT CURRENT_TIMESTAMP,
    admin_level   TEXT    DEFAULT 'national',
    province_code TEXT,
    province_name TEXT,
    disease_category TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_src_dis_reg_date
    ON disease_stats(source_key, disease_name, region, stat_date);

CREATE INDEX IF NOT EXISTS idx_disease_date ON disease_stats(disease_name, stat_date);
CREATE INDEX IF NOT EXISTS idx_region_date  ON disease_stats(region, stat_date);
CREATE INDEX IF NOT EXISTS idx_level_province ON disease_stats(admin_level, province_name);
CREATE INDEX IF NOT EXISTS idx_category ON disease_stats(disease_category);

CREATE TABLE IF NOT EXISTS realtime_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_name TEXT,
    region       TEXT,
    metric_name  TEXT,
    metric_value REAL,
    snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


DEFAULT_SOURCES = [
    ("nhc_cn", "国家卫健委全国月报", "adapters.nhc_cn.NhcCnAdapter", 1, 604800),
    ("gd_cn",  "广东省卫健委月报",   "adapters.gd_province.GdProvinceAdapter", 1, 604800),
    ("zj_cn",  "浙江省卫健委月报",   "adapters.zj_province.ZjProvinceAdapter", 1, 604800),
    ("js_cn",  "江苏省卫健委月报",   "adapters.js_province.JsProvinceAdapter", 1, 604800),
    ("sd_cn",  "山东省卫健委月报",   "adapters.sd_province.SdProvinceAdapter", 1, 604800),
]


def init_db():
    """建表 + 注册数据源。幂等。"""
    log.info(f"初始化数据库：{DB_PATH}")
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)

        # 注册数据源（已存在则跳过）
        cur = conn.cursor()
        for key, name, cls, enabled, interval in DEFAULT_SOURCES:
            cur.execute(
                """INSERT OR IGNORE INTO data_sources
                   (source_key, display_name, adapter_class, enabled, crawl_interval_seconds)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, name, cls, enabled, interval),
            )
        conn.commit()
    finally:
        conn.close()

    log.info("数据库初始化完成")


def is_empty() -> bool:
    """检查数据库是否为空（用于首次启动判断）。"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM disease_stats")
        return cur.fetchone()[0] == 0
    except sqlite3.OperationalError:
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()