"""侦察广东省卫健委月报：
   1. 从详情页找到 docx 附件下载链接
   2. 从栏目页找到历史月报列表
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

# 已知的一个详情页（你之前跑出来的）
DETAIL_URL = "https://wsjkw.gd.gov.cn/gkmlpt/content/4/4942/post_4942475.html"

# 尝试几个可能的列表页 URL
LIST_CANDIDATES = [
    "https://wsjkw.gd.gov.cn/gkmlpt/index#2571",
    "https://wsjkw.gd.gov.cn/gkmlpt/index",
    "https://wsjkw.gd.gov.cn/zwgk_ywtz/index.html",
    "https://wsjkw.gd.gov.cn/zwgk/index.html",
    "https://wsjkw.gd.gov.cn/zwgk_xxgk/index.html",
]


def fetch(client, url):
    resp = client.get(url)
    resp.raise_for_status()
    if resp.encoding.lower() in ("iso-8859-1", "ascii"):
        resp.encoding = resp.charset_encoding or "utf-8"
    return resp.text


def probe_detail(client):
    print("=" * 70)
    print("【1】详情页里的 docx / 附件链接")
    print("=" * 70)
    html = fetch(client, DETAIL_URL)
    soup = BeautifulSoup(html, "lxml")

    found_any = False
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # 匹配 docx / doc / pdf / 附件
        if re.search(r"\.(docx?|pdf|xlsx?|zip)$", href, re.I) or "附件" in text:
            full = urljoin(DETAIL_URL, href)
            print(f"  [{text[:60]}]")
            print(f"      → {full}")
            found_any = True

    if not found_any:
        print("  ⚠️  未在页面 <a> 里找到 docx 链接")
        # 尝试从原始 HTML 里正则搜
        print()
        print("  尝试从原始 HTML 正则搜：")
        for m in re.finditer(r'["\']([^"\']*\.docx?)["\']', html, re.I):
            print(f"      → {m.group(1)}")

    print()
    print("=" * 70)
    print("【2】详情页里所有含 'download' 或 'attach' 的链接")
    print("=" * 70)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "download" in href.lower() or "attach" in href.lower():
            print(f"  → {urljoin(DETAIL_URL, href)}")


def probe_lists(client):
    print()
    print("=" * 70)
    print("【3】探测可能的栏目列表页")
    print("=" * 70)
    for url in LIST_CANDIDATES:
        try:
            resp = client.get(url)
            status = resp.status_code
            print(f"  HTTP {status}  {url}")
            if status == 200:
                if resp.encoding.lower() in ("iso-8859-1", "ascii"):
                    resp.encoding = resp.charset_encoding or "utf-8"
                soup = BeautifulSoup(resp.text, "lxml")
                # 找含"法定传染病"的链接
                hits = 0
                for a in soup.find_all("a", href=True):
                    text = a.get_text(strip=True)
                    if "法定传染病" in text or "疫情" in text:
                        full = urljoin(url, a["href"])
                        print(f"      [{text[:50]}] → {full}")
                        hits += 1
                        if hits >= 5:
                            break
                if hits == 0:
                    print(f"      （无相关链接，可能列表页 URL 不对）")
        except Exception as e:
            print(f"  失败  {url}  →  {e}")


if __name__ == "__main__":
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        probe_detail(client)
        probe_lists(client)