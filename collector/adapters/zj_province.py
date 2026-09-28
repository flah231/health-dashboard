"""浙江省法定传染病疫情适配器。

数据源：浙江省卫健委「疫情播报」栏目
页面结构：完整的 52 行 HTML 统计表
"""
import json
import re
import calendar
from datetime import date
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

from adapters.base import BaseAdapter, DiseaseRecord
from diseases_catalog import ALL_DISEASES, DISEASE_TO_CATEGORY, SKIP_ROWS

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class ZjProvinceAdapter(BaseAdapter):
    source_key = "zj_cn"
    admin_level = "province"
    province_code = "330000"
    province_name = "浙江省"

    # 栏目列表页（从详情页 URL 反推）
    LIST_BASE = "https://wsjkw.zj.gov.cn/col/col1229123469"
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
        """用 jpaas API 发现浙江月报链接。"""
        seen: set[str] = set()
        ordered: list[str] = []

        API_URL = "https://wsjkw.zj.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit"

        # 从首页 HTML 的 queryData 中提取的参数
        BASE_PARAMS = {
            "parseType": "bulidstatic",
            "webId": "1855",
            "tplSetId": "ZVCGeuevPb8hqjUdWoxn1",
            "pageType": "column",
            "tagId": "当前栏目列表1a",
            "editType": "null",
            "pageId": "1229123469",
        }

        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            # 先访问首页获取 cookie
            try:
                client.get(f"{self.LIST_BASE}/index.html")
            except Exception:
                pass

            for page in range(1, self.MAX_PAGES + 1):
                params = dict(BASE_PARAMS)
                # 分页参数通过 paramJson 传递
                params["paramJson"] = json.dumps(
                    {"pageNo": page, "pageSize": 26}
                )

                try:
                    resp = client.get(API_URL, params=params)
                    resp.raise_for_status()
                except Exception as e:
                    print(f"   ⏹️  API 第 {page} 页请求失败：{e}")
                    break

                try:
                    data = resp.json()
                    html_fragment = data.get("data", {}).get("html", "")
                except Exception as e:
                    print(f"   ⏹️  API 第 {page} 页 JSON 解析失败：{e}")
                    break

                if not html_fragment:
                    print(f"   📄 API 第 {page} 页：0 条，停止翻页")
                    break

                # 从 HTML 片段中提取月报链接
                found = 0
                for m in re.finditer(
                    r'href="(/col/col1229123469/art/\d+/art_[a-f0-9]+\.html)"',
                    html_fragment,
                ):
                    path = m.group(1)
                    full = urljoin("https://wsjkw.zj.gov.cn", path)
                    if full in seen:
                        continue
                    seen.add(full)
                    ordered.append(full)
                    found += 1

                # 兼容旧格式 /art/2025/7/11/art_1229123469_xxxx.html
                for m in re.finditer(
                    r'href="(/art/\d{4}/\d+/\d+/art_1229123469_\d+\.html)"',
                    html_fragment,
                ):
                    path = m.group(1)
                    full = urljoin("https://wsjkw.zj.gov.cn", path)
                    if full in seen:
                        continue
                    seen.add(full)
                    ordered.append(full)
                    found += 1

                print(f"   📄 API 第 {page} 页：{found} 条新链接")
                if found == 0:
                    break

        return ordered

    def _process_report(self, client: httpx.Client, url: str):
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 提取标题（兼容浙江新旧两种 URL 格式，页面结构基本一致）
        title = soup.title.string if soup.title else ""
        stat_date = self._extract_stat_date(title)
        if not stat_date:
            return []

        # 找行数最多的表格（疾病统计表 52 行）
        tables = soup.find_all("table")
        if not tables:
            return []
        stat_table = max(tables, key=lambda t: len(t.find_all("tr")))

        merged: dict[str, dict] = {}
        for tr in stat_table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            name = self._normalize(cells[0])
            if not name:
                continue
            try:
                confirmed = int(re.sub(r"[^\d]", "", cells[1]) or 0)
                deaths = int(re.sub(r"[^\d]", "", cells[2]) or 0)
            except ValueError:
                continue
            bucket = merged.setdefault(name, {"confirmed": 0, "deaths": 0})
            bucket["confirmed"] += confirmed
            bucket["deaths"] += deaths

        return self._build(merged, stat_date)

    @staticmethod
    def _extract_stat_date(text: str) -> date | None:
        m = re.search(r"(\d{4})年(\d{1,2})月", text)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        return date(y, mo, calendar.monthrange(y, mo)[1])

    @staticmethod
    def _normalize(raw: str) -> str | None:
        raw = raw.strip()
        if not raw or raw in SKIP_ROWS:
            return None
        if raw in ALL_DISEASES:
            return raw
        aliases = {
            "其它感染性腹泻病": "感染性腹泻病",
            "其他感染性腹泻病": "感染性腹泻病",
            "甲乙丙类总计": None, "甲乙类合计": None, "丙类合计": None,
            "乙肝": "病毒性肝炎", "丙肝": "病毒性肝炎", "甲肝": "病毒性肝炎",
            "戊肝": "病毒性肝炎", "丁肝": "病毒性肝炎",
            "脊灰": "脊髓灰质炎", "乙脑": "流行性乙型脑炎",
            "出血热": "流行性出血热", "布病": "布鲁氏菌病",
            "钩体病": "钩端螺旋体病", "斑疹伤寒": "流行性和地方性斑疹伤寒",
            "痢疾": "细菌性和阿米巴性痢疾", "流脑": "流行性脑脊髓膜炎",
        }
        if raw in aliases:
            return aliases[raw]
        for d in ALL_DISEASES:
            if d in raw:
                return d
        return None

    def _build(self, merged: dict, stat_date: date) -> list[DiseaseRecord]:
        return [
            DiseaseRecord(
                source_key=self.source_key,
                disease_name=name,
                region="浙江省",
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