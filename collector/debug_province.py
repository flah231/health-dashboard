"""通用省级月报侦察工具。

用法：
    python debug_province.py <省份标识> <月报URL>

示例：
    python debug_province.py zj https://wsjkw.zj.gov.cn/art/xxx.html
    python debug_province.py js http://wjw.jiangsu.gov.cn/xxx.html
    python debug_province.py sd http://wsjkw.shandong.gov.cn/xxx.html

输出：
    1. 页面标题、HTML 结构
    2. 是否有 docx/pdf 附件
    3. 有多少个 <table>，每个表多少行
    4. 是否含"统计表"关键字
    5. 是否含"前5位"文字描述
    6. 是否含"其他感染性腹泻病"等疾病名
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

DISEASE_HINTS = [
    "肺结核", "病毒性肝炎", "艾滋病", "梅毒", "淋病",
    "流行性感冒", "手足口病", "其他感染性腹泻病",
    "新型冠状病毒感染", "鼠疫", "霍乱",
]


def probe(province: str, url: str):
    print("=" * 72)
    print(f"【{province.upper()}】{url}")
    print("=" * 72)

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        html = resp.text

    soup = BeautifulSoup(html, "lxml")

    # 1. 标题
    title = soup.title.string.strip() if soup.title and soup.title.string else "（无 title）"
    print(f"\n【1】页面标题：{title}")

    # 2. 页面里含关键疾病名
    text = soup.get_text(separator="\n", strip=True)
    found_diseases = [d for d in DISEASE_HINTS if d in text]
    print(f"\n【2】页面里找到 {len(found_diseases)} 种疾病名：")
    print(f"    {'、'.join(found_diseases) if found_diseases else '（无）'}")

    # 3. 是否含"前5位/前3位"
    has_rank = "前5位" in text or "前3位" in text
    print(f"\n【3】是否含'前5位/前3位'文字描述：{'✅ 是' if has_rank else '❌ 否'}")

    # 4. docx / pdf / xlsx 附件
    print(f"\n【4】页面里的附件链接：")
    attachments = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(docx?|pdf|xlsx?|zip)$", href, re.I):
            full = urljoin(url, href)
            attachments.append((a.get_text(strip=True), full))
    if attachments:
        for t, h in attachments[:8]:
            print(f"    📎 {t[:50]}")
            print(f"       → {h}")
    else:
        print("    （无）")

    # 5. 所有 table 的规模
    print(f"\n【5】页面里的表格：")
    tables = soup.find_all("table")
    print(f"    共 {len(tables)} 个 <table>")
    for i, t in enumerate(tables, 1):
        rows = t.find_all("tr")
        print(f"    table {i}: {len(rows)} 行")
        # 打印前 3 行
        for tr in rows[:3]:
            cells = [c.get_text(strip=True)[:30] for c in tr.find_all(["td", "th"])]
            print(f"      {cells}")

    # 6. 是否含"统计表"关键标题
    has_stat_table = "统计表" in text
    print(f"\n【6】是否含'统计表'关键字：{'✅ 是' if has_stat_table else '❌ 否'}")

    # 7. 正文里含"甲乙丙类传染病总计"或"法定传染病"的区域
    print(f"\n【7】关键段落预览：")
    for kw in ["甲乙丙类传染病总计", "全省共报告", "共报告发病", "法定传染病"]:
        idx = text.find(kw)
        if idx >= 0:
            snippet = text[idx:idx + 120].replace("\n", " ")
            print(f"    「{kw}」→ {snippet}")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python debug_province.py <省份标识> <月报URL>")
        print("      省份标识：zj / js / sd")
        sys.exit(1)
    probe(sys.argv[1], sys.argv[2])