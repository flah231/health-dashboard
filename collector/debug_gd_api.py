"""诊断广东 JSONP 接口 —— 直接打印原始响应，看看到底返回了什么。"""
import json
from urllib.parse import quote

import httpx

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://wsjkw.gd.gov.cn/gkmlpt/search",
}

# 依次测试多种可能的 URL 格式
CANDIDATES = [
    # 1. 从源码里看到的 jsonp 接口
    {
        "name": "search.gd.gov.cn/jsonp/site/216",
        "url": "https://search.gd.gov.cn/jsonp/site/216",
        "params": {
            "page": 1, "pagesize": 20,
            "text": "法定传染病疫情概况",
            "order": 0, "position": "title",
            "callback": "success",
        },
    },
    # 2. search.gd.gov.cn/jsonp + site 参数
    {
        "name": "search.gd.gov.cn/jsonp?site=216",
        "url": "https://search.gd.gov.cn/jsonp",
        "params": {
            "site": 216, "page": 1, "pagesize": 20,
            "text": "法定传染病疫情概况",
            "order": 0, "position": "title",
            "callback": "success",
        },
    },
    # 3. 可能的其他接口
    {
        "name": "wsjkw.gd.gov.cn/gkmlpt/api/search",
        "url": "https://wsjkw.gd.gov.cn/gkmlpt/api/search",
        "params": {
            "keywords": "法定传染病疫情概况",
            "page": 1, "pageSize": 20,
            "order": 0, "position": "title",
        },
    },
    # 4. jsonp + siteId (驼峰)
    {
        "name": "search.gd.gov.cn/jsonp/site/216 (siteId)",
        "url": "https://search.gd.gov.cn/jsonp/site/216",
        "params": {
            "page": 1, "pagesize": 20,
            "text": "法定传染病疫情概况",
            "order": 0, "position": "title",
            "callback": "success",
        },
    },
]


def probe(client, candidate):
    name = candidate["name"]
    url = candidate["url"]
    params = candidate["params"]
    print("\n" + "=" * 70)
    print(f"【测试】{name}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print("-" * 70)
    try:
        resp = client.get(url, params=params, timeout=20)
        print(f"HTTP {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', '?')}")
        print(f"响应长度: {len(resp.text)} 字符")
        print()
        print("【响应前 1000 字符】")
        print(resp.text[:1000])
        print()
        # 尝试解析 JSON
        text = resp.text
        if text.startswith("success("):
            json_str = text[len("success("):-2] if text.endswith(");") else text[len("success("):-1]
            try:
                data = json.loads(json_str)
                print("【JSON 解析成功】顶层 keys:", list(data.keys()))
                for k, v in data.items():
                    if isinstance(v, list):
                        print(f"   {k}: list, 长度 {len(v)}")
                        if v:
                            print(f"      第一条 keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
                    else:
                        print(f"   {k}: {str(v)[:100]}")
            except Exception as e:
                print(f"【JSON 解析失败】{e}")
    except Exception as e:
        print(f"❌ 请求异常：{e}")


if __name__ == "__main__":
    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for c in CANDIDATES:
            probe(client, c)