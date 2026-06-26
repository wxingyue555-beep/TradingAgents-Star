"""检查宏观新闻实际读取的内容"""
from tradingagents.dataflows.local_news_api import _query_news

print("=== 宏观快讯查询详情 ===")
print()

# 第一天的请求
items, total = _query_news(date='2026-06-26', limit=45, order_by='date DESC')
print(f"date=2026-06-26: total={total}, returned={len(items)}")
codes = set()
for it in items:
    codes.add(it.get("code", ""))
print(f"涉及股票数: {len(codes)}")
print(f"涉及股票: {sorted(codes)[:15]}")
print()

# 第二天的请求
items2, total2 = _query_news(date='2026-06-25', limit=45, order_by='date DESC')
print(f"date=2026-06-25: total={total2}, returned={len(items2)}")
codes2 = set()
for it in items2:
    codes2.add(it.get("code", ""))
print(f"涉及股票数: {len(codes2)}")
print()

# 检查分类分布
cats = {}
for it in items:
    c = it.get("category", "未知")
    cats[c] = cats.get(c, 0) + 1
print("2026-06-26 分类分布:")
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {n}")

# 显示前5条
print()
print("前5条:")
for i, it in enumerate(items[:5]):
    print(f"  [{it['category']}] {it['code']} {it['stock_name']} {it['stars']}")
    print(f"    {it['title'][:80]}")
