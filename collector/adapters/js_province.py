"""江苏省法定传染病疫情适配器（v4：doc/docx 双格式 + Word COM 复用）。

策略（按优先级）：
1. .docx → python-docx 直接解析
2. .doc → 用 Word COM 接口转换（复用全局 Word 实例）→ python-docx 解析
3. 失败 → 解析页面 HTML 表格
4. 都失败 → 增强正则从正文提取（含"无发病"的疾病）
"""
import re
import os
import calendar
import tempfile
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

ZIP_MAGIC = b"PK\x03\x04"       # .docx
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"  # .doc


# ---- 全局 Word 实例（复用，避免反复启动） ----
_WORD_APP = None


def _get_word_app():
    """惰性获取 Word.Application 单例。"""
    global _WORD_APP
    if _WORD_APP is not None:
        try:
            # 试探是否还活着
            _ = _WORD_APP.Version
            return _WORD_APP
        except Exception:
            _WORD_APP = None

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        return None

    try:
        pythoncom.CoInitialize()
        _WORD_APP = win32com.client.DispatchEx("Word.Application")
        _WORD_APP.Visible = False
        _WORD_APP.DisplayAlerts = False
        return _WORD_APP
    except Exception as e:
        print(f"      ⚠️ 无法启动 Word：{e}")
        _WORD_APP = None
        return None


def convert_doc_to_docx(doc_bytes: bytes) -> bytes | None:
    """用 Word COM 把 .doc 转成 .docx（复用同一个 Word 实例）。"""
    word = _get_word_app()
    if word is None:
        return None

    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
        f.write(doc_bytes)
        doc_path = f.name
    docx_path = doc_path[:-4] + ".docx"

    try:
        wd = word.Documents.Open(doc_path, ReadOnly=True)
        # 16 = wdFormatXMLDocument (.docx)
        wd.SaveAs2(docx_path, FileFormat=16)
        wd.Close(False)
        with open(docx_path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"      ⚠️ Word 转换失败：{str(e)[:60]}")
        return None
    finally:
        for p in (doc_path, docx_path):
            try:
                os.unlink(p)
            except Exception:
                pass


def cleanup_word():
    """适配器结束后调用。"""
    global _WORD_APP
    if _WORD_APP is not None:
        try:
            _WORD_APP.Quit()
        except Exception:
            pass
        _WORD_APP = None


class JsProvinceAdapter(BaseAdapter):
    source_key = "js_cn"
    admin_level = "province"
    province_code = "320000"
    province_name = "江苏省"

    LIST_BASE = "http://wjw.jiangsu.gov.cn/col/col49513"
    MAX_PAGES = 30
    MAX_REPORTS = 200

    # ---------------- 主流程 ----------------

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
                        source = recs[0].extra.get("data_source", "?")
                        print(f"   [{i}/{len(urls)}] ✅ {month} "
                              f"[{source}] → {len(recs)} 种疾病")
                    else:
                        print(f"   [{i}/{len(urls)}] ⚠️  跳过")
                except Exception as e:
                    print(f"   [{i}/{len(urls)}] ❌ {str(e)[:80]}")

        cleanup_word()
        return records

    # ---------------- 发现列表 ----------------

    def _discover_report_urls(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            page_urls = [f"{self.LIST_BASE}/index.html"]
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

                found = 0
                for m in re.finditer(
                    r"/art/\d{4}/\d+/\d+/art_49513_\d+\.html",
                    resp.text,
                ):
                    path = m.group(0)
                    full = urljoin(page_url, path)
                    if full in seen:
                        continue
                    seen.add(full)
                    ordered.append(full)
                    found += 1

                print(f"   📄 {page_url.split('/')[-1]}：{found} 条")
                if found == 0:
                    break
        return ordered

    # ---------------- 处理单个月报 ----------------

    def _process_report(self, client: httpx.Client, url: str):
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        title = soup.title.string if soup.title else ""
        stat_date = self._extract_stat_date(title)
        if not stat_date:
            m = re.search(r"/art/(\d{4})/(\d+)/", url)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                stat_date = date(y, mo, calendar.monthrange(y, mo)[1])
        if not stat_date:
            return []

        merged: dict[str, dict] = {}
        data_source = None

        # ---- 找附件 ----
        docx_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if "统计表" in text and (".doc" in href.lower() or "downfile" in href.lower()):
                docx_url = urljoin(url, href)
                break

        # ---- 策略 1+2：doc/docx ----
        if docx_url:
            doc = None
            try:
                docx_resp = client.get(
                    docx_url,
                    follow_redirects=True,
                    headers={"Referer": url},
                )
                docx_resp.raise_for_status()
                raw = docx_resp.content

                if raw[:4] == ZIP_MAGIC:
                    doc = Document(BytesIO(raw))
                    data_source = "docx"
                elif raw[:4] == OLE2_MAGIC:
                    # 老 .doc → 用 Word COM 转换（复用全局实例）
                    converted = convert_doc_to_docx(raw)
                    if converted:
                        doc = Document(BytesIO(converted))
                        data_source = "doc_via_word"
                else:
                    print(f"      ⚠️ 未知文件签名：{raw[:4]!r}")
            except Exception as e:
                print(f"      ⚠️ doc 处理失败：{str(e)[:60]}")

            if doc and doc.tables:
                for row in doc.tables[0].rows:
                    cells = [c.text.strip() for c in row.cells]
                    if len(cells) < 3:
                        continue
                    self._merge_row(cells[0], cells[1], cells[2], merged)
                if not merged:
                    data_source = None  # 解析空表 → 降级

        # ---- 策略 3：HTML 表格 ----
        if not merged:
            tables = soup.find_all("table")
            if tables:
                stat_table = max(tables, key=lambda t: len(t.find_all("tr")))
                if len(stat_table.find_all("tr")) >= 10:
                    for tr in stat_table.find_all("tr"):
                        cells = [c.get_text(strip=True)
                                 for c in tr.find_all(["td", "th"])]
                        if len(cells) < 3:
                            continue
                        self._merge_row(cells[0], cells[1], cells[2], merged)
                    if merged:
                        data_source = "html_table"

        # ---- 策略 4：增强正则 ----
        if not merged:
            text = soup.get_text(separator="\n", strip=True)
            merged = self._extract_from_text(text)
            if merged:
                data_source = "text_rank"

        if not merged:
            return []

        return self._build(merged, stat_date, data_source)

    # ---------------- 辅助 ----------------

    def _merge_row(self, raw_name: str, confirmed_str: str, deaths_str: str, merged: dict):
        name = self._normalize(raw_name)
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

    def _extract_from_text(self, text: str) -> dict:
        """增强正则：从正文里抓所有提及的疾病名 + 前 N 位排名。"""
        merged: dict[str, dict] = {}

        # 匹配"前N位病种依次为：X、Y、Z"
        for m in re.finditer(
            r"(?:报告发病数居前|报告死亡数居前)\s*([0-9一二三四五六七八九十]+)\s*位[的]?病种依次[为:：]?\s*"
            r"([^\。]+?)(?=占|。|，同期|$)",
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
                merged.setdefault(name, {"confirmed": 0, "deaths": 0, "rank": rank})

        # 匹配"XX、YY、ZZ 无发病、死亡报告"（疾病值为 0）
        for m in re.finditer(
            r"([^\。；]+?)(?:无发病|未报告发病|无报告发病)",
            text,
        ):
            segment = m.group(1)
            names = re.split(r"[、,，及和\s]+", segment)
            for raw in names:
                raw = raw.strip()
                if not raw or len(raw) > 15:
                    continue
                name = self._normalize(raw)
                if not name:
                    continue
                bucket = merged.setdefault(name, {"confirmed": 0, "deaths": 0})
                bucket.setdefault("is_zero", True)

        return merged

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
        aliases = {
            "其它感染性腹泻病": "感染性腹泻病",
            "其他感染性腹泻病": "感染性腹泻病",
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

    def _build(self, merged: dict, stat_date: date, data_source: str) -> list[DiseaseRecord]:
        return [
            DiseaseRecord(
                source_key=self.source_key,
                disease_name=name,
                region="江苏省",
                stat_date=stat_date,
                confirmed=vals["confirmed"],
                cured=0,
                deaths=vals["deaths"],
                extra={
                    "stat_month": stat_date.strftime("%Y-%m"),
                    "data_source": data_source,
                    "rank": vals.get("rank"),
                    "is_zero": vals.get("is_zero", False),
                },
                admin_level="province",
                province_code=self.province_code,
                province_name=self.province_name,
                disease_category=DISEASE_TO_CATEGORY.get(name),
            )
            for name, vals in merged.items()
        ]