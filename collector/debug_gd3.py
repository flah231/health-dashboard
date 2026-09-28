"""侦察广东省：
   1. 搜索接口的分页规律
   2. 4 月页面的 HTML 结构（是 table 还是纯文本）
"""
import re
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 4 月页面（无 docx 附件，正文里有表格）
DETAIL_URL_4M = "https://wsjkw.gd.gov.cn/gkmlpt/content/4/4942/post_4942475.html"

# 尝试搜索接口的多种 URL 形态
SEARCH_BASE = "https://wsjkw.gd.gov.cn/gkmlpt/search"


def fetch(client, url):
    resp = client.get(url)
    resp.raise_for_status()
    if resp.encoding.lower() in ("iso-8859-1", "ascii"):
        resp.encoding = resp.charset_encoding or "utf-8"
    return resp.text


def probe_search_pages(client):
    print("=" * 70)
    print("【1】搜索接口分页侦察")
    print("=" * 70)

    # 搜索关键词：法定传染病疫情概况
    kw = quote("法定传染病疫情概况")
    candidates = [
        f"{SEARCH_BASE}?keywords={kw}&order=0&position=title",
        f"{SEARCH_BASE}?keywords={kw}&order=0&position=title&page=2",
        f"{SEARCH_BASE}?keywords={kw}&order=0&position=title&pageIndex=2",
        f"{SEARCH_BASE}?keywords={kw}&order=0&position=title&p=2",
    ]
    for url in candidates:
        try:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, "lxml")
            # 找含"法定传染病"的链接
            hits = []
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                if "法定传染病" in text and "疫情" in text:
                    hits.append((text[:40], a["href"]))
            print(f"\n  URL: {url[:100]}...")
            print(f"  HTTP {resp.status_code}，找到 {len(hits)} 条月报链接")
            for t, h in hits[:3]:
                print(f"    · {t}")
            # 找分页控件
            for a in soup.find_all("a", href=True):
                t = a.get_text(strip=True)
                if t in ("下一页", "2", "3", "尾页"):
                    print(f"    分页控件：{t} → {a['href'][:80]}")
        except Exception as e:
            print(f"  ❌ {url}  失败：{e}")


def probe_detail_html(client):
    print()
    print("=" * 70)
    print("【2】4 月页面的 HTML 结构")
    print("=" * 70)
    html = fetch(client, DETAIL_URL_4M)
    soup = BeautifulSoup(html, "lxml")

    # 找所有 table
    tables = soup.find_all("table")
    print(f"  页面共 {len(tables)} 个 <table>")
    for i, t in enumerate(tables):
        print(f"    table {i+1}: {len(t.find_all('tr'))} 行")
        # 打印前 3 行
        for tr in t.find_all("tr")[:3]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            print(f"      {cells}")

    # 找含"统计表"或"甲乙丙类传染病总计"的容器
    print()
    print("  --- 找含『甲乙丙类传染病总计』的元素 ---")
    target = soup.find(string=re.compile("甲乙丙类传染病总计"))
    if target:
        parent = target.find_parent()
        # 往上找
        node = parent
        for _ in range(4):
            print(f"    父元素 <{node.name}> class={node.get('class')}")
            print(f"      文本长度：{len(node.get_text(strip=True))}")
            node = node.parent
            if node is None:
                break
        # 打印父容器的原始 HTML 前 1500 字
        if parent:
            ancestor = parent.find_parent()
            if ancestor:
                print()
                print("  --- 父容器原始 HTML 前 1500 字 ---")
                print(ancestor.prettify()[:1500])
    else:
        print("    ⚠️  没找到含此关键字的元素")


if __name__ == "__main__":
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        probe_search_pages(client)
        probe_detail_html(client)