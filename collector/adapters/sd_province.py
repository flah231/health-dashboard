"""山东省法定传染病疫情适配器。

数据源：山东省卫健委「法定报告传染病」栏目
页面结构：无表格、无附件，只有文字描述
策略：鲁棒提取"共报告发病XXX例" + "居前N位的病种依次为..."
      总计记录保留真实数字，排名记录仅存排名，数值置 0
"""
import re
import calendar
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from adapters.base import BaseAdapter, DiseaseRecord
from diseases_catalog import ALL_DISEASES, DISEASE_TO_CATEGORY

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class SdProvinceAdapter(BaseAdapter):
    source_key = "sd_cn"
    admin_level = "province"
    province_code = "370000"
    province_name = "山东省"

    LIST_BASE = "http://wsjkw.shandong.gov.cn/zwgk/zdmsgysy/fdcrb"
    MAX_PAGES = 30
    MAX_REPORTS = 200

    def fetch(self) -> list[DiseaseRecord]:
        urls = self._discover_report_urls()
        if not urls:
            raise RuntimeError("未发现任何月报链接")
        print(f"   🔗 共发现 {len(urls)} 个候选详情页")

        records: list[DiseaseRecord] = []
        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
            for i, url in enumerate(urls[:self.MAX_REPORTS], 1):
                try:
                    recs = self._process_report(client, url)
                    if recs:
                        records.extend(recs)
                        month = recs[0].extra.get("stat_month", "?")
                        print(f"   [{i}/{len(urls)}] ✅ {month} → {len(recs)} 种疾病")
                    else:
                        print(f"   [{i}/{len(urls)}] ⚠️  跳过")
                except Exception as e:
                    print(f"   [{i}/{len(urls)}] ❌ {e}")
        return records

    def _discover_report_urls(self) -> list[str]:
        """山东栏目页 URL 格式：/YYYYMM/tYYYYMMDD_xxxxx.html（按月目录）。"""
        seen: set[str] = set()
        ordered: list[str] = []

        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            page_urls = [f"{self.LIST_BASE}/"]
            for i in range(1, self.MAX_PAGES):
                page_urls.append(f"{self.LIST_BASE}/index_{i}.html")

            for page_url in page_urls:
                try:
                    resp = client.get(page_url)
                    if resp.status_code != 200:
                        break
                    if resp.encoding.lower() in ("iso-8859-1", "ascii"):
                        resp.encoding = resp.charset_encoding or "utf-8"
                except Exception:
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                found = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if "法定" not in text and "传染病" not in text and "疫情" not in text:
                        continue
                    full = urljoin(page_url, href)
                    if full in seen:
                        continue
                    seen.add(full)
                    ordered.append(full)
                    found += 1
                print(f"   📄 {page_url.split('/')[-1] or 'index'}：{found} 条")
                if found == 0:
                    break
        return ordered

    def _process_report(self, client: httpx.Client, url: str):
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        title = soup.title.string if soup.title else ""
        stat_date = self._extract_stat_date(title)
        if not stat_date:
            m = re.search(r"/(\d{4})(\d{2})/t\d{8}", url)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                stat_date = date(y, mo, calendar.monthrange(y, mo)[1])
        if not stat_date:
            return []

        text = soup.get_text(separator="\n", strip=True)
        records: list[DiseaseRecord] = []

        # ---- 提取总计（鲁棒版） ----
        total_confirmed, total_deaths = self._extract_total(text)
        if total_confirmed and total_confirmed > 1000:
            records.append(self._make_total_record(
                stat_date, total_confirmed, total_deaths))

        # ---- 提取"前 N 位"疾病（只有排名，无数字） ----
        ranked = self._extract_ranked_diseases(text)
        for name, rank in ranked:
            records.append(self._make_ranked_record(stat_date, name, rank))

        return records

    def _extract_total(self, text: str) -> tuple[int, int]:
        """从正文提取总计，用最鲁棒的方式：找所有"XXX例"里的最大值，
        以及"死亡XX人"里的值。"""
        # 所有含"例"的数字，取最大的（山东省人口 1 亿，月报至少几万）
        confirmed_candidates = [
            int(m.group(1))
            for m in re.finditer(r"(\d+)\s*例", text)
            if int(m.group(1)) > 1000
        ]
        confirmed = max(confirmed_candidates) if confirmed_candidates else 0

        # 死亡数：找"死亡"后面的数字，取最大的一个（但要排除累计死亡）
        deaths_candidates = [
            int(m.group(1))
            for m in re.finditer(r"死亡\s*(\d+)\s*[人例]", text)
            if int(m.group(1)) < 10000
        ]
        deaths = max(deaths_candidates) if deaths_candidates else 0

        return confirmed, deaths

    def _extract_ranked_diseases(self, text: str) -> list[tuple[str, int]]:
        """返回 [(疾病名, 排名), ...]。"""
        result: list[tuple[str, int]] = []

        for m in re.finditer(
            r"报告发病数居前\s*([0-9一二三四五六七八九十]+)\s*位[的]?病种依次[为:：]?\s*"
            r"([^\。占]+?)(?=占|。|，同期|$)",
            text,
        ):
            top_n_str = m.group(1)
            cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                      "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            try:
                top_n = int(top_n_str)
            except ValueError:
                top_n = cn_map.get(top_n_str, 5)

            segment = m.group(2)
            names = re.split(r"[、,，及和\s]+", segment)
            names = [n.strip() for n in names if n.strip()]
            for rank, raw in enumerate(names[:top_n], 1):
                name = self._normalize(raw)
                if not name:
                    continue
                result.append((name, rank))
        return result

    def _make_total_record(self, stat_date: date,
                           confirmed: int, deaths: int) -> DiseaseRecord:
        """总计记录：真正有数字。"""
        return DiseaseRecord(
            source_key=self.source_key,
            disease_name="甲乙丙类传染病总计",
            region="山东省",
            stat_date=stat_date,
            confirmed=confirmed,
            cured=0,
            deaths=deaths,
            extra={
                "stat_month": stat_date.strftime("%Y-%m"),
                "record_type": "total",
            },
            admin_level="province",
            province_code=self.province_code,
            province_name=self.province_name,
            disease_category=None,
        )

    def _make_ranked_record(self, stat_date: date,
                             name: str, rank: int) -> DiseaseRecord:
        """排名记录：值未知，用 NULL 语义（这里用 None），
           前端会根据 record_type='ranked' 过滤掉。"""
        return DiseaseRecord(
            source_key=self.source_key,
            disease_name=name,
            region="山东省",
            stat_date=stat_date,
            confirmed=0,
            cured=0,
            deaths=0,
            extra={
                "stat_month": stat_date.strftime("%Y-%m"),
                "record_type": "ranked",
                "rank": rank,
            },
            admin_level="province",
            province_code=self.province_code,
            province_name=self.province_name,
            disease_category=DISEASE_TO_CATEGORY.get(name),
        )

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
        if not raw:
            return None
        if raw in ALL_DISEASES:
            return raw
        aliases = {
            "其它感染性腹泻病": "感染性腹泻病",
            "其他感染性腹泻病": "感染性腹泻病",
            "乙肝": "病毒性肝炎", "丙肝": "病毒性肝炎",
            "脊灰": "脊髓灰质炎", "乙脑": "流行性乙型脑炎",
            "布病": "布鲁氏菌病", "钩体病": "钩端螺旋体病",
        }
        if raw in aliases:
            return aliases[raw]
        for d in ALL_DISEASES:
            if d in raw:
                return d
        return None