"""写入 MySQL/SQLite 的标准化记录。"""
import json
from db import get_conn
from adapters.base import DiseaseRecord


def upsert_records(records: list[DiseaseRecord]) -> int:
    """写入或更新记录。SQLite 用 ON CONFLICT DO UPDATE。"""
    if not records:
        return 0

    conn = get_conn()
    affected = 0
    try:
        cur = conn.cursor()
        for r in records:
            cur.execute(
                """
                INSERT INTO disease_stats
                    (source_key, disease_name, region, stat_date,
                     confirmed, cured, deaths, extra_json,
                     admin_level, province_code, province_name, disease_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key, disease_name, region, stat_date)
                DO UPDATE SET
                    confirmed        = excluded.confirmed,
                    cured            = excluded.cured,
                    deaths           = excluded.deaths,
                    extra_json       = excluded.extra_json,
                    disease_category = excluded.disease_category,
                    crawl_time       = CURRENT_TIMESTAMP
                """,
                (
                    r.source_key, r.disease_name, r.region, str(r.stat_date),
                    r.confirmed, r.cured, r.deaths,
                    json.dumps(r.extra, ensure_ascii=False) if r.extra else None,
                    r.admin_level, r.province_code, r.province_name,
                    r.disease_category,
                ),
            )
            affected += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return affected