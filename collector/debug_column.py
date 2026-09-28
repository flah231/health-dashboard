"""侦察省级栏目列表页结构（v2 强化版）。

用法：
    python debug_column.py <栏目URL> <省份>
"""
import re
import sys
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def probe(url: str, province: str):
    print("=" * 72)
    print(f"【{province}】{url}")
    print("=" * 72)

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        print(f"HTTP {resp.status_code}")
        print(f"最终 URL：{resp.url}")
        print(f"页面大小：{len(resp.text)} 字符")
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        html = resp.text

    soup = BeautifulSoup(html, "lxml")

    if soup.title:
        print(f"标题：{soup.title.string}")

    # ---- 1. 正则搜 HTML 里所有 .html 链接 ----
    print("\n【1】正则搜 HTML 里所有 .html 链接（去重前 30 条）：")
    html_links = set()
    for m in re.finditer(r'(?:href|src|url)\s*=\s*["\']([^"\']+\.html?[^"\']*)["\']', html, re.I):
        html_links.add(m.group(1))
    for l in list(html_links)[:30]:
        print(f"   {l}")
    print(f"   共 {len(html_links)} 个唯一链接")

    # ---- 2. 所有含"art_"的字符串 ----
    print("\n【2】正则搜 HTML 里所有含 'art_' 的字符串（前 15 条）：")
    art_pattern = re.compile(r'[^"\'\s]*art_[^"\'\s]*')
    art_hits = set()
    for m in art_pattern.finditer(html):
        art_hits.add(m.group(0)[:120])
    for h in list(art_hits)[:15]:
        print(f"   {h}")
    print(f"   共 {len(art_hits)} 个唯一字符串")

    # ---- 3. 所有含"传染病"或"疫情"的 <a> ----
    print("\n【3】含'法定/传染病/疫情'的 <a> 标签（前 15 条）：")
    hits = 0
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if any(k in text for k in ("法定", "传染病", "疫情")):
            print(f"   [{text[:50]}]")
            print(f"      href={a['href']}")
            hits += 1
            if hits >= 15:
                break
    if hits == 0:
        print("   ❌ <a> 标签里找不到，说明是 JS 动态渲染")

    # ---- 4. iframe 检查 ----
    print("\n【4】页面里的 iframe：")
    iframes = soup.find_all("iframe")
    if iframes:
        for ifr in iframes[:5]:
            print(f"   src={ifr.get('src')}")
    else:
        print("   （无）")

    # ---- 5. 分页控件 ----
    print("\n【5】分页控件：")
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if text in ("下一页", "尾页", "末页", "2", "3"):
            print(f"   [{text}] → {a['href']}")

    # ---- 6. 页面里的 JavaScript 文件 ----
    print("\n【6】加载的 JS 文件（前 10 个）：")
    for s in soup.find_all("script", src=True)[:10]:
        print(f"   {s['src']}")

    # ---- 7. 页面里是否有 JSON 数据 ----
    print("\n【7】HTML 里的 JSON 数据线索：")
    for kw in ['"list"', '"data"', '"items"', '"total"', "getJSON", "$.get", "$.post", "$.ajax"]:
        if kw in html:
            print(f"   ⚠️  发现 '{kw}'")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python debug_column.py <栏目URL> <省份>")
        sys.exit(1)
    probe(sys.argv[1], sys.argv[2])