"""通用页面侦察工具。

用法：
    python debug_page.py <URL>

它会：
    1. 抓取页面并保存 HTML 到 collector/debug/ 目录
    2. 打印正文文本前 3000 字（去掉 script/style）
    3. 打印所有表格的前几个，方便分析结构
"""
import sys
from datetime import datetime
from pathlib import Path

import httpx

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def fetch_and_save(url: str):
    debug_dir = Path(__file__).parent / "debug"
    debug_dir.mkdir(exist_ok=True)

    print(f"🌐 正在抓取：{url}")
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

        # 中文站点有些是 GBK，httpx 有时识别错误
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"

        html = resp.text
        print(f"📄 页面大小：{len(html)} 字符")
        print(f"🔤 编码识别：{resp.encoding}")

        # 保存原始 HTML
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = debug_dir / f"page_{ts}.html"
        out.write_text(html, encoding="utf-8")
        print(f"💾 已保存：{out}")

        # 解析
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        print("\n" + "=" * 60)
        print("📝 正文文本预览（前 3000 字）：")
        print("=" * 60)
        print(text[:3000])
        print("=" * 60)

        # 表格
        tables = soup.find_all("table")
        print(f"\n📊 页面包含 {len(tables)} 个 <table>")
        for i, t in enumerate(tables[:3]):
            print(f"\n--- 表格 {i + 1} 前 800 字符 ---")
            print(str(t)[:800])

        # 表格行数
        for i, t in enumerate(tables[:3]):
            rows = t.find_all("tr")
            print(f"\n📋 表格 {i + 1} 共 {len(rows)} 行")
            for j, tr in enumerate(rows[:5]):
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                print(f"   行 {j + 1}: {cells}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python debug_page.py <URL>")
        sys.exit(1)
    fetch_and_save(sys.argv[1])