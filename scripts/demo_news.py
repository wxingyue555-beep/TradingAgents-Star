from tradingagents.dataflows.local_news_api import get_local_news_api, get_local_global_news_api

print("=" * 60)
print("个股新闻: 002471 (中超控股)")
print("=" * 60)
print(get_local_news_api("002471", "2026-06-19", "2026-06-26"))

print()
print("=" * 60)
print("宏观快讯: 近3天全市场利好 Top 8")
print("=" * 60)
print(get_local_global_news_api("2026-06-26", look_back_days=3, limit=8))
