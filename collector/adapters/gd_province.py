"""广东省法定传染病疫情概况适配器（v5 双策略发现版）。

策略：
1. 使用官方 JSONP 接口，通过栏目 ID 全量拉取 + 多关键词搜索补充，最大程度发现月报
2. 访问详情页时，从 <span class="document-number"> 提取标题，解析统计月份
3. 优先解析 docx 附件；无附件时降级解析页面第 2 个 HTML 表格
"""
import json
import re
import calendar
from datetime import date
from io import BytesIO
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from docx import Document

from adapters.base import BaseAdapter, DiseaseRecord
from diseases_catalog import ALL_DISEASES, DISEASE_TO_CATEGORY, SKIP_ROWS

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 详情页 URL 正则（兜底过滤，防止接口返回无关页面）
DETAIL_URL_PATTERN = re.compile(r"/gkmlpt/content/\d+/\d+/post_\d+\.html")
BASE_HOST = "https://wsjkw.gd.gov.cn"


class GdProvinceAdapter(BaseAdapter):
    source_key = "gd_cn"
    admin_level = "province"
    province_code = "440000"
    province_name = "广东省"

    # 官方 JSONP 搜索接口
    SEARCH_API = "https://search.gd.gov.cn/jsonp/site/216"
    MAX_PAGES = 20
    MAX_REPORTS = 300

    # ---------------- 主流程 ----------------

    def fetch(self) -> list[DiseaseRecord]:
        urls = self._discover_report_urls()
        if not urls:
            raise RuntimeError("未发现任何月报链接，请检查搜索接口是否变化")

        print(f"   🔗 共发现 {len(urls)} 个候选详情页")
        records: list[DiseaseRecord] = []

        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
            for i, detail_url in enumerate(urls[:self.MAX_REPORTS], 1):
                try:
                    recs = self._process_report(client, detail_url)
                    if recs:
                        records.extend(recs)
                        # 从第一条记录拿月份做日志
                        month = recs[0].extra.get("stat_month", "?")
                        print(f"   [{i}/{len(urls)}] ✅ {month} → {len(recs)} 种疾病")
                    else:
                        print(f"   [{i}/{len(urls)}] ⚠️  跳过（无有效数据）")
                except Exception as e:
                    print(f"   [{i}/{len(urls)}] ❌ 解析失败：{e}")
        return records

    # ---------------- 发现月报链接 ----------------

    def _discover_report_urls(self) -> list[str]:
        """双策略发现月报 URL：
           策略1：按栏目 classify_main=2571 拉全部（最全）
           策略2：多关键词搜索补充（覆盖新旧标题）
        """
        seen: set[str] = set()
        ordered: list[str] = []

        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
            # ---- 策略 1：按栏目 ID 直接拉全部 ----
            print("   🔍 策略1：按栏目 classify_main=2571")
            for page in range(1, self.MAX_PAGES + 1):
                params = {
                    "classify_main": 2571,
                    "page": page,
                    "pagesize": 20,
                    "callback": "success",
                }
                data = self._jsonp_get(client, params, page)
                if data is None:
                    break
                results = data.get("results", [])
                if not results:
                    print(f"      第 {page} 页：0 条，停止")
                    break
                found = self._collect_urls(results, seen, ordered)
                print(f"      第 {page} 页：{found} 条新链接")
                if page * 20 >= data.get("count", 0):
                    break

            # ---- 策略 2：多关键词搜索补充 ----
            KEYWORDS = ["法定传染病疫情概况", "法定报告传染病疫情"]
            for kw in KEYWORDS:
                print(f"   🔍 策略2：搜索关键词「{kw}」")
                for page in range(1, self.MAX_PAGES + 1):
                    params = {
                        "text": kw,
                        "page": page,
                        "pagesize": 20,
                        "order": 0,
                        "position": "title",
                        "callback": "success",
                    }
                    data = self._jsonp_get(client, params, page)
                    if data is None:
                        break
                    results = data.get("results", [])
                    if not results:
                        break
                    found = self._collect_urls(results, seen, ordered)
                    print(f"      第 {page} 页：{found} 条新链接")
                    if found == 0 or page * 20 >= data.get("count", 0):
                        break

        return ordered

    def _jsonp_get(self, client: httpx.Client, params: dict, page: int) -> dict | None:
        """带重试的 JSONP 请求。"""
        for attempt in (1, 2):
            try:
                resp = client.get(self.SEARCH_API, params=params)
                resp.raise_for_status()
                break
            except Exception as e:
                if attempt == 2:
                    print(f"      第 {page} 页失败：{e}")
                    return None
                import time
                time.sleep(2)
        # 剥 JSONP 外壳
        text = resp.text.strip()
        if text.startswith("success("):
            text = text[len("success("):]
            if text.endswith(");"):
                text = text[:-2]
            elif text.endswith(")"):
                text = text[:-1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _collect_urls(results: list, seen: set, ordered: list) -> int:
        """从结果里筛月报、去重、加入 ordered。返回新加数量。"""
        found = 0
        for item in results:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            # 兼容两种标题格式
            if not any(k in title for k in ("法定传染病", "法定报告传染病", "疫情概况")):
                continue
            seen.add(url)
            ordered.append(url)
            found += 1
        return found

    # ---------------- 解析单个详情页 ----------------

    def _process_report(self, client: httpx.Client, detail_url: str):
        resp = client.get(detail_url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 提取标题 → 统计月份
        title = self._extract_title(soup)
        if not title:
            return []
        stat_date = self._extract_stat_date(title)
        if not stat_date:
            return []

        # 尝试找 docx 附件
        docx_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if "统计表" in text and href.endswith(".docx"):
                docx_url = urljoin(detail_url, href)
                break

        merged: dict[str, dict] = {}

        if docx_url:
            # ---- 走 docx 解析 ----
            try:
                docx_resp = client.get(docx_url)
                docx_resp.raise_for_status()
                doc = Document(BytesIO(docx_resp.content))
                if doc.tables:
                    self._extract_from_rows(doc.tables[0].rows, merged)
            except Exception as e:
                print(f"      docx 解析失败：{e}")
                return []
        else:
            # ---- 降级：解析页面第 2 个 HTML 表格 ----
            tables = soup.find_all("table")
            if len(tables) >= 2:
                # 表 1 是元数据，表 2 是疾病统计
                # 但保险起见：找行数最多的那个表
                stat_table = max(tables, key=lambda t: len(t.find_all("tr")))
                self._extract_from_html_rows(stat_table.find_all("tr"), merged)

        return self._build_records(merged, stat_date)

    @staticmethod
    def _extract_from_rows(rows, merged: dict):
        """从 docx 表格的行里提取数据。"""
        for row in rows:
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) < 3:
                continue
            GdProvinceAdapter._merge_row(cells[0], cells[1], cells[2], merged)

    @staticmethod
    def _extract_from_html_rows(rows, merged: dict):
        """从 HTML 表格的行里提取数据。"""
        for tr in rows:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            GdProvinceAdapter._merge_row(cells[0], cells[1], cells[2], merged)

    @staticmethod
    def _merge_row(raw_name: str, confirmed_str: str, deaths_str: str, merged: dict):
        name = GdProvinceAdapter._normalize_disease(raw_name)
        if not name:
            return
        try:
            confirmed = int(re.sub(r"[^\d]", "", confirmed_str) or 0)
            deaths = int(re.sub(r"[^\d]", "", deaths_str) or 0)
        except ValueError:
            return
        bucket = merged.setdefault(name, {"confirmed": 0, "deaths": 0})
        bucket["confirmed"] += confirmed
        bucket["deaths"] += deaths

    def _build_records(self, merged: dict, stat_date: date) -> list[DiseaseRecord]:
        return [
            DiseaseRecord(
                source_key=self.source_key,
                disease_name=name,
                region="广东省",
                stat_date=stat_date,
                confirmed=vals["confirmed"],
                cured=0,
                deaths=vals["deaths"],
                extra={"stat_month": stat_date.strftime("%Y-%m")},
                admin_level="province",
                province_code=self.province_code,
                province_name=self.province_name,
                disease_category=DISEASE_TO_CATEGORY.get(name),
            )
            for name, vals in merged.items()
        ]

    # ---------------- 工具 ----------------

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str | None:
        """从页面提取月报标题。"""
        # 优先：<span class="document-number" title="...">
        el = soup.find("span", class_="document-number")
        if el and el.get("title"):
            return el["title"]
        # 兜底：<title> 标签
        if soup.title and soup.title.string:
            return soup.title.string
        # 再兜底：找含"法定传染病"的元素
        node = soup.find(string=re.compile(r"\d{4}年\d{1,2}月.*法定传染病"))
        if node:
            return str(node)[:120]
        return None

    @staticmethod
    def _extract_stat_date(title: str) -> date | None:
        m = re.search(r"(\d{4})年(\d{1,2})月", title)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        if not (1 <= mo <= 12):
            return None
        return date(y, mo, calendar.monthrange(y, mo)[1])

    @staticmethod
    def _normalize_disease(raw: str) -> str | None:
        raw = raw.strip()
        if not raw or raw in SKIP_ROWS:
            return None
        if raw in ALL_DISEASES:
            return raw
        aliases = {
            "其它感染性腹泻病": "感染性腹泻病",
            "其他感染性腹泻病": "感染性腹泻病",
            "乙肝": "病毒性肝炎",
            "丙肝": "病毒性肝炎",
            "甲肝": "病毒性肝炎",
            "戊肝": "病毒性肝炎",
            "丁肝": "病毒性肝炎",
            "肝炎（未分型）": "病毒性肝炎",
            "脊灰": "脊髓灰质炎",
            "乙脑": "流行性乙型脑炎",
            "出血热": "流行性出血热",
            "布病": "布鲁氏菌病",
            "钩体病": "钩端螺旋体病",
            "斑疹伤寒": "流行性和地方性斑疹伤寒",
            "痢疾": "细菌性和阿米巴性痢疾",
            "流脑": "流行性脑脊髓膜炎",
        }
        if raw in aliases:
            return aliases[raw]
        for d in ALL_DISEASES:
            if d in raw:
                return d
        return None