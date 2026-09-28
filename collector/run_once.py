"""手动运行适配器。

用法：
    python run_once.py                    # 运行全部
    python run_once.py nhc_cn             # 只运行国家卫健委
    python run_once.py nhc_cn gd_cn       # 运行多个
"""
import sys
import traceback

from registry import discover_adapters
from storage import upsert_records


def main(argv: list[str]) -> int:
    adapters = discover_adapters()
    if not adapters:
        print("❌ 未发现任何适配器")
        return 1

    # 命令行筛选
    if argv:
        wanted = set(argv)
        adapters = {k: v for k, v in adapters.items() if k in wanted}
        if not adapters:
            print(f"❌ 未找到指定的适配器：{wanted}")
            return 1

    print(f"🔍 将运行 {len(adapters)} 个适配器：")
    for key, cls in adapters.items():
        print(f"   • {key:15s} → {cls.__name__}")
    print()

    total_records = 0
    total_written = 0
    failed = []

    for key, cls in adapters.items():
        print(f"▶ 开始抓取 [{key}] ...")
        try:
            adapter = cls()
            records = adapter.fetch()
            print(f"   抓取到 {len(records)} 条记录")
            affected = upsert_records(records)
            total_records += len(records)
            total_written += affected
            print(f"   ✅ 已写入数据库")
        except Exception as e:
            print(f"   ❌ 抓取失败：{e}")
            traceback.print_exc()
            failed.append(key)
        print()

    print("=" * 55)
    print(f"📊 总计：抓取 {total_records} 条，写入 {total_written} 条")
    if failed:
        print(f"⚠️  失败：{', '.join(failed)}")
        return 1
    print("✅ 全部成功")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))