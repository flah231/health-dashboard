"""测试解析中国疾控中心月报页面（修复版 v2）。

用法：
    python parse_test.py <URL>
"""
import re
import sys
import calendar
from datetime import date

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 40 种法定传染病完整目录
CLASS_A = ["鼠疫", "霍乱"]
CLASS_B = [
    "新型冠状病毒感染", "传染性非典型肺炎", "艾滋病", "病毒性肝炎",
    "脊髓灰质炎", "人感染新亚型流感", "麻疹", "流行性出血热",
    "狂犬病", "流行性乙型脑炎", "登革热", "猴痘", "炭疽",
    "细菌性和阿米巴性痢疾", "肺结核", "伤寒和副伤寒",
    "流行性脑脊髓膜炎", "百日咳", "白喉", "新生儿破伤风",
    "猩红热", "布鲁氏菌病", "淋病", "梅毒",
    "钩端螺旋体病", "血吸虫病", "疟疾",
]
CLASS_C = [
    "流行性感冒", "流行性腮腺炎", "风疹", "急性出血性结膜炎",
    "麻风病", "流行性和地方性斑疹伤寒", "黑热病", "包虫病",
    "丝虫病", "手足口病", "感染性腹泻病",
]
ALL_DISEASES = set(CLASS_A + CLASS_B + CLASS_C)

# 页面写法 → 目录标准名
ALIASES = {
    "其他感染性腹泻病":      "感染性腹泻病",
    "人感染高致病性禽流感":  "人感染新亚型流感",
    "人感染H7N9禽流感":      "人感染新亚型流感",
}

# 需要跳过的汇总行
SKIP_NAMES = {
    "病名", "甲乙丙类传染病总计", "甲乙类传染病合计", "丙类传染病合计",
}

# 病毒性肝炎的子项（不在 40 种目录里，应跳过）
VIRAL_HEPATITIS_SUB = {
    "甲型肝炎", "乙型肝炎", "丙型肝炎", "丁型肝炎", "戊型肝炎", "未分型肝炎",
}


def normalize_disease(raw: str) -> str | None:
    """把页面上的疾病名映射到标准目录名。"""
    raw = raw.strip()
    if not raw:
        return None
    if raw in SKIP_NAMES or raw in VIRAL_HEPATITIS_SUB:
        return None
    if raw in ALL_DISEASES:
        return raw
    if raw in ALIASES:
        return ALIASES[raw]
    for d in ALL_DISEASES:
        if d in raw:
            return d
    for alias, real in ALIASES.items():
        if alias in raw:
            return real
    return None


def parse_page(url: str):
    print(f"🌐 抓取：{url}")
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        if resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.charset_encoding or "utf-8"
        html = resp.text

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n", strip=True)

    # 提取统计月份
    stat_date = None
    m = re.search(r"(\d{4})年(\d{1,2})月", text)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        stat_date = date(y, mo, calendar.monthrange(y, mo)[1])
    print(f"📅 识别统计月份：{stat_date}\n")

    table = soup.find("table")
    if not table:
        print("❌ 未找到表格")
        return

    print(f"{'疾病':<24}{'发病数':>14}{'死亡数':>10}")
    print("─" * 60)

    found = []

    for tr in table.find_all("tr"):
        # 先删除 <sup> 上标注释编号（比如"艾滋病²"）
        for sup in tr.find_all("sup"):
            sup.decompose()

        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue

        # 关键修复：直接按单元格取值，不再拼字符串
        name_raw = cells[0].get_text(strip=True)
        confirmed_raw = cells[1].get_text(strip=True)
        deaths_raw = cells[2].get_text(strip=True)

        disease = normalize_disease(name_raw)
        if not disease:
            continue

        # 只接受纯数字（防止匹配到"0"以外的异常字符）
        if not re.fullmatch(r"\d+", confirmed_raw):
            continue
        if not re.fullmatch(r"\d+", deaths_raw):
            continue

        confirmed = int(confirmed_raw)
        deaths = int(deaths_raw)
        found.append((disease, confirmed, deaths))
        print(f"{disease:<24}{confirmed:>14,}{deaths:>10,}")

    print("─" * 60)
    print(f"✅ 匹配到 {len(found)} / 40 种疾病\n")

    found_names = {d for d, _, _ in found}
    missing = ALL_DISEASES - found_names
    if missing:
        print("⚠️  未匹配到的疾病：")
        print("   " + "、".join(sorted(missing)))
    else:
        print("🎉 40 种疾病全部匹配成功！")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python parse_test.py <URL>")
        sys.exit(1)
    parse_page(sys.argv[1])