"""侦察中国疾控中心月报列表页的分页结构。

用法：
    python debug_list.py
"""
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

LIST_URL = "https://www.chinacdc.cn/jksj/jksj01/"


def probe():
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(LIST_URL)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        print("=" * 70)
        print("【1】页面里所有包含 'index_' 或 'page' 的链接")
        print("=" * 70)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if ("index_" in href or "/page" in href.lower()
                    or "下一页" in text or "尾页" in text
                    or "首页" in text or "末页" in text):
                print(f"  [{text}] → {href}")

        print()
        print("=" * 70)
        print("【2】疑似分页容器 HTML")
        print("=" * 70)
        # 找到含"下一页"的元素，往上找容器
        next_btn = soup.find("a", string=lambda s: s and "下一页" in s)
        if next_btn:
            container = next_btn.find_parent(class_=True)
            if container:
                print(container.prettify()[:2500])
            else:
                parent = next_btn.find_parent()
                print(parent.prettify()[:2500])
        else:
            print("⚠️  未找到含'下一页'的链接")

        print()
        print("=" * 70)
        print("【3】列表页正文里的月报链接（前 5 条样例）")
        print("=" * 70)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if ("法定传染病" in text and "疫情" in text) or \
               ("t20" in href and href.endswith(".html")):
                print(f"  [{text[:40]}] → {href}")
                # 只打印前 5 条样例
        print()

        print("=" * 70)
        print("【4】尝试直接访问常见的分页 URL，看哪个能返回 200")
        print("=" * 70)
        candidates = [
            "index_1.html", "index_2.html", "index_3.html",
            "index_1.shtml", "index_2.shtml",
            "index_1.htm", "index_2.htm",
        ]
        for c in candidates:
            url = urljoin(LIST_URL, c)
            try:
                r = client.head(url, follow_redirects=True)
                print(f"  {c:20s} → HTTP {r.status_code}  {url}")
            except Exception as e:
                print(f"  {c:20s} → 失败：{e}")


if __name__ == "__main__":
    probe()