"""侦察广东省月报栏目：
   1. 列表页能翻几页、每页多少条
   2. 每个详情页到底有没有 docx/pdf 附件
"""
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

LIST_URL = "https://cdcp.gd.gov.cn/ywdt/tfggwssj/index.html"


def probe_list_pages(client):
    print("=" * 70)
    print("【1】列表页翻页侦察")
    print("=" * 70)
    all_reports = []
    for i in range(0, 12):
        url = LIST_URL if i == 0 else urljoin(LIST_URL, f"index_{i}.html")
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                print(f"  第{i+1:2d}页: HTTP {resp.status_code} → 停止")
                break
            if resp.encoding.lower() in ("iso-8859-1", "ascii"):
                resp.encoding = resp.charset_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            reports_on_page = []
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                if "法定传染病" in text or "疫情概况" in text:
                    full = urljoin(url, a["href"])
                    reports_on_page.append((text, full))
            print(f"  第{i+1:2d}页: {len(reports_on_page):2d} 个月报")
            for t, _ in reports_on_page[:2]:
                print(f"          · {t[:50]}")
            all_reports.extend(reports_on_page)
        except Exception as e:
            print(f"  第{i+1:2d}页: 失败 {e}")
            break
    print(f"\n  合计发现 {len(all_reports)} 个月报\n")
    return all_reports


def probe_details(client, reports):
    print("=" * 70)
    print("【2】每个详情页的附件情况（只看最近 8 条）")
    print("=" * 70)
    for idx, (title, url) in enumerate(reports[:8], 1):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            if resp.encoding.lower() in ("iso-8859-1", "ascii"):
                resp.encoding = resp.charset_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            attachments = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if re.search(r"\.(docx?|pdf|xlsx?)", href, re.I):
                    attachments.append((text, urljoin(url, href)))

            print(f"\n  [{idx}] {title[:55]}")
            if attachments:
                for t, h in attachments:
                    print(f"      📎 {t[:50]}")
                    print(f"         → {h}")
            else:
                print(f"      ⚠️  页面里找不到任何 docx/pdf 附件")
        except Exception as e:
            print(f"\n  [{idx}] {title[:55]}  →  ❌ {e}")


if __name__ == "__main__":
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        reports = probe_list_pages(client)
        probe_details(client, reports)