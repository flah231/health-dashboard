"""统计查询 API（SQLite 版）。"""
from typing import Optional
from fastapi import APIRouter, Query
from db import get_conn

router = APIRouter()


def _latest_year(cur) -> Optional[int]:
    cur.execute("SELECT MAX(CAST(strftime('%Y', stat_date) AS INTEGER)) AS y FROM disease_stats")
    row = cur.fetchone()
    return row["y"] if row and row["y"] else None


def _build_where(year, source_key, region, disease):
    clauses, params = [], []
    if year:
        clauses.append("CAST(strftime('%Y', stat_date) AS INTEGER) = ?"); params.append(year)
    if source_key:
        clauses.append("source_key = ?"); params.append(source_key)
    if region:
        clauses.append("region = ?"); params.append(region)
    if disease:
        clauses.append("disease_name = ?"); params.append(disease)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


@router.get("/filters")
def get_filters():
    conn = get_conn()
    try:
        cur = conn.cursor()

        # 年份：从 disease_stats 查（只有有数据的年份才显示）
        cur.execute("""
            SELECT DISTINCT CAST(strftime('%Y', stat_date) AS INTEGER) AS y
            FROM disease_stats
            ORDER BY y DESC
        """)
        years = [r["y"] for r in cur.fetchall()]

        # 数据源：从 data_sources 查（所有启用的源都显示，无论有没有数据）
        cur.execute("""
            SELECT source_key FROM data_sources
            WHERE enabled = 1
            ORDER BY source_key
        """)
        sources = [r["source_key"] for r in cur.fetchall()]

        # 地区：从 disease_stats 查
        cur.execute("SELECT DISTINCT region FROM disease_stats ORDER BY region")
        regions = [r["region"] for r in cur.fetchall()]

        # 疾病：从 disease_stats 查
        cur.execute("SELECT DISTINCT disease_name FROM disease_stats ORDER BY disease_name")
        diseases = [r["disease_name"] for r in cur.fetchall()]
    finally:
        conn.close()

    return {
        "years": years,
        "sources": sources,
        "regions": regions,
        "diseases": diseases,
    }


@router.get("/overview")
def overview(year: Optional[int] = Query(None), source_key: Optional[str] = Query(None)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        effective_year = year if year is not None else _latest_year(cur)
        where, params = _build_where(effective_year, source_key, None, None)
        cur.execute(f"""
            SELECT
                COALESCE(SUM(confirmed), 0)  AS confirmed,
                COALESCE(SUM(cured), 0)      AS cured,
                COALESCE(SUM(deaths), 0)     AS deaths,
                COUNT(DISTINCT disease_name) AS disease_count,
                COUNT(DISTINCT region)       AS region_count,
                COUNT(DISTINCT strftime('%Y-%m', stat_date)) AS month_count
            FROM disease_stats {where}
        """, params)
        row = cur.fetchone()
    finally:
        conn.close()
    return {
        "year": effective_year,
        "confirmed":    int(row["confirmed"]),
        "cured":        int(row["cured"]),
        "deaths":       int(row["deaths"]),
        "diseaseCount": int(row["disease_count"]),
        "regionCount":  int(row["region_count"]),
        "monthCount":   int(row["month_count"]),
    }


@router.get("/trend")
def trend(days: int = Query(30, ge=1, le=365), source_key: Optional[str] = Query(None)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        where, params = _build_where(None, source_key, None, None)
        extra = " AND " if where else " WHERE "
        cur.execute(f"""
            SELECT stat_date AS date,
                   SUM(confirmed) AS confirmed,
                   SUM(cured)     AS cured,
                   SUM(deaths)    AS deaths
            FROM disease_stats
            {where}{extra}stat_date >= date('now', '-{int(days)} day')
            GROUP BY stat_date
            ORDER BY stat_date
        """, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"date": r["date"], "confirmed": int(r["confirmed"]),
         "cured": int(r["cured"]), "deaths": int(r["deaths"])}
        for r in rows
    ]


@router.get("/yearly")
def yearly(source_key: Optional[str] = Query(None)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        where, params = _build_where(None, source_key, None, None)
        cur.execute(f"""
            SELECT CAST(strftime('%Y', stat_date) AS INTEGER) AS year,
                   SUM(confirmed) AS confirmed,
                   SUM(cured)     AS cured,
                   SUM(deaths)    AS deaths
            FROM disease_stats
            {where}
            GROUP BY year
            ORDER BY year
        """, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"year": int(r["year"]), "confirmed": int(r["confirmed"]),
         "cured": int(r["cured"]), "deaths": int(r["deaths"])}
        for r in rows
    ]


@router.get("/monthly")
def monthly(
    months: int = Query(24, ge=1, le=120),
    source_key: Optional[str] = Query(None),
    disease_name: Optional[str] = Query(None),
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        where, params = _build_where(None, source_key, None, disease_name)
        extra = " AND " if where else " WHERE "
        cur.execute(f"""
            SELECT strftime('%Y-%m', stat_date) AS month,
                   SUM(confirmed) AS confirmed,
                   SUM(deaths)    AS deaths
            FROM disease_stats
            {where}{extra}stat_date >= date('now', '-{int(months)} month')
            GROUP BY month
            ORDER BY month
        """, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"month": r["month"], "confirmed": int(r["confirmed"]), "deaths": int(r["deaths"])}
        for r in rows
    ]


@router.get("/ranking")
def ranking(
    year: Optional[int] = Query(None),
    source_key: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        effective_year = year if year is not None else _latest_year(cur)
        where, params = _build_where(effective_year, source_key, None, None)
        extra = " AND " if where else " WHERE "
        cur.execute(f"""
            SELECT disease_name AS diseaseName,
                   SUM(confirmed) AS confirmed,
                   SUM(cured)     AS cured,
                   SUM(deaths)    AS deaths
            FROM disease_stats
            {where}{extra}COALESCE(json_extract(extra_json, '$.record_type'), '') != 'ranked'
            GROUP BY disease_name
            ORDER BY confirmed DESC
            LIMIT ?
        """, params + [limit])
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"diseaseName": r["diseaseName"], "confirmed": int(r["confirmed"]),
         "cured": int(r["cured"]), "deaths": int(r["deaths"])}
        for r in rows
    ]


@router.get("/categories")
def categories(
    year: Optional[int] = Query(None),
    source_key: Optional[str] = Query(None),
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        effective_year = year if year is not None else _latest_year(cur)
        where, params = _build_where(effective_year, source_key, None, None)
        extra = " AND " if where else " WHERE "
        cur.execute(f"""
            SELECT COALESCE(disease_category, '未分类') AS category,
                   SUM(confirmed) AS confirmed,
                   SUM(deaths)    AS deaths,
                   COUNT(DISTINCT disease_name) AS disease_count
            FROM disease_stats
            {where}{extra}disease_category IS NOT NULL
            GROUP BY category
            ORDER BY CASE category
                WHEN '甲' THEN 1
                WHEN '乙' THEN 2
                WHEN '丙' THEN 3
                ELSE 4
            END
        """, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"category": r["category"], "confirmed": int(r["confirmed"]),
         "deaths": int(r["deaths"]), "diseaseCount": int(r["disease_count"])}
        for r in rows
    ]


@router.get("/regions")
def regions(
    year: Optional[int] = Query(None),
    source_key: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        effective_year = year if year is not None else _latest_year(cur)
        where, params = _build_where(effective_year, source_key, None, None)
        cur.execute(f"""
            SELECT region, SUM(confirmed) AS confirmed, SUM(deaths) AS deaths
            FROM disease_stats {where}
            GROUP BY region ORDER BY confirmed DESC LIMIT ?
        """, params + [limit])
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"region": r["region"], "confirmed": int(r["confirmed"]), "deaths": int(r["deaths"])}
        for r in rows
    ]


@router.get("/detail")
def detail(
    year: Optional[int] = Query(None),
    source_key: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        where, params = _build_where(year, source_key, None, None)
        extra = " AND " if where else " WHERE "
        filter_clause = (
            f"{where}{extra}COALESCE(json_extract(extra_json, '$.record_type'), '') != 'ranked'"
        )
        cur.execute(f"SELECT COUNT(*) AS total FROM disease_stats {filter_clause}", params)
        total = cur.fetchone()["total"]

        offset = (page - 1) * page_size
        cur.execute(f"""
            SELECT source_key, disease_name, region, stat_date,
                   confirmed, cured, deaths
            FROM disease_stats
            {filter_clause}
            ORDER BY stat_date DESC, confirmed DESC
            LIMIT ? OFFSET ?
        """, params + [page_size, offset])
        rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "total": int(total), "page": page, "pageSize": page_size,
        "items": [
            {"source": r["source_key"], "diseaseName": r["disease_name"],
             "region": r["region"], "date": r["stat_date"],
             "confirmed": int(r["confirmed"]), "cured": int(r["cured"]),
             "deaths": int(r["deaths"])}
            for r in rows
        ],
    }