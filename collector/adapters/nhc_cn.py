"""中国疾控中心「全国法定传染病疫情概况」适配器。

流程：
    1. 从栏目列表页发现所有月报详情页 URL
    2. 逐个抓取详情页，解析底部统计表
    3. 返回标准化的 DiseaseRecord 列表

列表页：https://www.chinacdc.cn/jksj/jksj01/
"""
import calendar
import re
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from adapters.base import BaseAdapter, DiseaseRecord
from diseases_catalog import (
    ALL_DISEASES, DISEASE_ALIASES, DISEASE_TO_CATEGORY, SKIP_ROWS,
)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class NhcCnAdapter(BaseAdapter):
    source_key = "nhc_cn"
    admin_level = "national"

    # 栏目列表页（可通过 config 覆盖）
    LIST_URL = "https://www.chinacdc.cn/jksj/jksj01/"
    MAX_PAGES = 50      # 最多探测 50 页（安全上限，实际遇到 404 就停）
    MAX_REPORTS = 500   # 最多抓 500 条月报（约 40 年，作为兜底上限）

    def fetch(self) -> list[DiseaseRecord]:
        urls = self._discover_report_urls()
        print(f"   🔗 发现 {len(urls)} 个月报链接")
        if not urls:
            raise RuntimeError("未发现任何月报链接，请检查列表页结构是否变化")

        records: list[DiseaseRecord] = []
        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for i, url in enumerate(urls[:self.MAX_REPORTS], 1):
                try:
                    month_records = self._parse_report(client, url)
                    if month_records:
                        records.extend(month_records)
                        print(f"   [{i}/{len(urls)}] ✅ {url.split('/')[-1]} → "
                              f"{len(month_records)} 种疾病")
                    else:
                        print(f"   [{i}/{len(urls)}] ⚠️  跳过（无有效数据）")
                except Exception as e:
                    print(f"   [{i}/{len(urls)}] ❌ 解析失败：{e}")
        return records

    # ---------- 列表页发现 ----------

    def _discover_report_urls(self) -> list[str]:
        """贪心翻页：从首页开始抓，遇到 404 或空页自动停止。

        分页规则（从侦察结果确认）：
            第 1 页：https://www.chinacdc.cn/jksj/jksj01/
            第 2 页：https://www.chinacdc.cn/jksj/jksj01/index_1.html
            第 3 页：https://www.chinacdc.cn/jksj/jksj01/index_2.html
            第 N 页：.../index_{N-1}.html
        """
        seen: set[str] = set()
        ordered: list[str] = []

        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            # 逐页探测：首页 + index_1 + index_2 + ... 直到 404
            page_urls = [self.LIST_URL]
            for i in range(1, self.MAX_PAGES + 1):
                page_urls.append(urljoin(self.LIST_URL, f"index_{i}.html"))

            for idx, page_url in enumerate(page_urls, 1):
                try:
                    resp = client.get(page_url)
                    if resp.status_code != 200:
                        print(f"   ⏹️  第 {idx} 页 HTTP {resp.status_code}，停止翻页")
                        break
                    if resp.encoding.lower() in ("iso-8859-1", "ascii"):
                        resp.encoding = resp.charset_encoding or "utf-8"
                except Exception as e:
                    print(f"   ⏹️  第 {idx} 页请求失败：{e}")
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                found_on_page = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if not re.search(r"/t\d{8}_\d+\.html$", href):
                        continue
                    if "法定传染病" not in text and "疫情" not in text:
                        continue
                    full = urljoin(page_url, href)
                    if full in seen:
                        continue
                    seen.add(full)
                    ordered.append(full)
                    found_on_page += 1

                print(f"   📄 第 {idx} 页（{page_url.split('/')[-1] or '首页'}）："
                      f"{found_on_page} 条新链接")

                if found_on_page == 0:
                    break

        return ordered

    # ---------- 详情页解析 ----------

    def _parse_report(self, client: httpx.Client, url: str) -> list[DiseaseRecord]:
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        text = soup.get_text(separator="\n", strip=True)
        stat_date = self._extract_stat_date(text)
        if not stat_date:
            return []

        table = soup.find("table")
        if not table:
            return []

        # 同一标准名可能出现多次（别名），先累加
        merged: dict[str, dict] = {}

        for tr in table.find_all("tr"):
            for sup in tr.find_all("sup"):
                sup.decompose()

            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            raw_name = cells[0].get_text(strip=True)
            confirmed_raw = cells[1].get_text(strip=True)
            deaths_raw = cells[2].get_text(strip=True)

            name = self._normalize(raw_name)
            if not name:
                continue
            if not re.fullmatch(r"\d+", confirmed_raw):
                continue
            if not re.fullmatch(r"\d+", deaths_raw):
                continue

            bucket = merged.setdefault(name, {"confirmed": 0, "deaths": 0})
            bucket["confirmed"] += int(confirmed_raw)
            bucket["deaths"] += int(deaths_raw)

        return [
            DiseaseRecord(
                source_key=self.source_key,
                disease_name=name,
                region="全国",
                stat_date=stat_date,
                confirmed=vals["confirmed"],
                cured=0,
                deaths=vals["deaths"],
                extra={"stat_month": stat_date.strftime("%Y-%m")},
                admin_level="national",
                disease_category=DISEASE_TO_CATEGORY.get(name),
            )
            for name, vals in merged.items()
        ]

    @staticmethod
    def _extract_stat_date(text: str) -> date | None:
        m = re.search(r"(\d{4})年(\d{1,2})月", text)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        if not (1 <= mo <= 12):
            return None
        return date(y, mo, calendar.monthrange(y, mo)[1])

    @staticmethod
    def _normalize(raw: str) -> str | None:
        raw = raw.strip()
        if not raw or raw in SKIP_ROWS:
            return None
        if raw in ALL_DISEASES:
            return raw
        if raw in DISEASE_ALIASES:
            return DISEASE_ALIASES[raw]
        for d in ALL_DISEASES:
            if d in raw:
                return d
        for alias, real in DISEASE_ALIASES.items():
            if alias in raw:
                return real
        return None