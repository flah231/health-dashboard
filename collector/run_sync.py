"""独立子进程：并发同步，支持 24 小时跳过。"""
import argparse
import io
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

# PyInstaller console=False 时 sys.stdout/stderr 为 None
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# PyInstaller 打包后，把解压目录加到 sys.path
if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, str(Path(__file__).parent))

import httpx

from registry import discover_adapters
from storage import upsert_records
from db import get_conn

BACKEND = "http://127.0.0.1:8000/api"

# 优先用后端统一的数据目录（打包后会传到 %APPDATA%\HealthDashboard\logs）
LOG_DIR_STR = os.getenv("HEALTH_LOG_DIR")
if LOG_DIR_STR:
    LOG_DIR = Path(LOG_DIR_STR)
else:
    LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "sync.log"
_log_fp = open(LOG_FILE, "a", encoding="utf-8")
_log_lock = threading.Lock()


def log(msg: str):
    with _log_lock:
        print(msg, flush=True)
        try:
            _log_fp.write(msg + "\n")
            _log_fp.flush()
        except Exception:
            pass


def _post(path: str, payload: dict):
    try:
        with httpx.Client(timeout=3) as client:
            client.post(f"{BACKEND}{path}", json=payload)
    except Exception:
        pass


def get_enabled_sources(source_filter=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if source_filter:
            cur.execute(
                "SELECT source_key FROM data_sources WHERE enabled = 1 AND source_key = ?",
                (source_filter,),
            )
        else:
            cur.execute("SELECT source_key FROM data_sources WHERE enabled = 1")
        return [r["source_key"] for r in cur.fetchall()]
    finally:
        conn.close()


def get_last_crawl(source_key):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT last_crawl_at FROM data_sources WHERE source_key = ?",
            (source_key,),
        )
        row = cur.fetchone()
        return row["last_crawl_at"] if row else None
    finally:
        conn.close()


def update_last_crawl(source_key):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE data_sources SET last_crawl_at = ? WHERE source_key = ?",
            (datetime.now().isoformat(timespec="seconds"), source_key),
        )
        conn.commit()
    finally:
        conn.close()


def should_skip(source_key, skip_hours):
    if skip_hours <= 0:
        return False
    last = get_last_crawl(source_key)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    return datetime.now() - last_dt < timedelta(hours=skip_hours)


def report_done(source_key, record_count, skipped=False):
    _post("/sync/source_done", {
        "source_key": source_key,
        "record_count": record_count,
        "skipped": skipped,
    })


def run_one(source_key, adapters, skip_hours):
    cls = adapters.get(source_key)
    if not cls:
        log(f"[WARN] {source_key} 未找到适配器")
        return source_key, 0, False

    if should_skip(source_key, skip_hours):
        log(f"[SKIP] {source_key}（{skip_hours}h 内已抓过）")
        report_done(source_key, 0, skipped=True)
        return source_key, 0, True

    log(f">>> 开始抓取 {source_key} ...")
    t0 = time.time()
    try:
        adapter = cls()
        records = adapter.fetch()
        if records:
            upsert_records(records)
        dt = time.time() - t0
        log(f"[OK] {source_key} 完成，{len(records)} 条，耗时 {dt:.1f}s")
        update_last_crawl(source_key)
        report_done(source_key, len(records))
        return source_key, len(records), False
    except Exception as e:
        import traceback
        log(f"[ERR] {source_key} 失败：{e}")
        log(traceback.format_exc())
        report_done(source_key, 0)
        return source_key, 0, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="只同步指定 source_key")
    parser.add_argument("--skip-hours", type=int, default=24,
                        help="多久内抓过的源跳过（默认 24 小时，0 = 不跳过）")
    args = parser.parse_args()

    log("\n" + "=" * 60)
    log(f"Sync started at {datetime.now()}  (skip_hours={args.skip_hours})")
    log("=" * 60)

    # 确保数据库表已创建（run_sync 独立运行时需要）
    try:
        from init_db import init_db
        init_db()
    except Exception as e:
        log(f"[WARN] 数据库初始化失败：{e}")

    adapters = discover_adapters()
    sources = get_enabled_sources(args.source)
    if not sources:
        log("没有启用的数据源")
        return

    log(f"共 {len(sources)} 个数据源（并发）：{sources}")
    _post("/sync/start", {"sources": sources})

    total_records = 0
    skipped_count = 0
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {
            executor.submit(run_one, key, adapters, args.skip_hours): key
            for key in sources
        }
        for fut in as_completed(futures):
            key, n, skipped = fut.result()
            total_records += n
            if skipped:
                skipped_count += 1

    _post("/sync/finish", {"total_records": total_records})
    log(f"\n[DONE] 全部完成，{total_records} 条，{skipped_count}/{len(sources)} 跳过")


if __name__ == "__main__":
    main()