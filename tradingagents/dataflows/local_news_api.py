"""本地新闻 API 客户端 — 通过 starweb.cpolar.io 或直接 SQLite 读取 news.db。

替代 china_news.py 的在线 HTTP 抓取（新浪/财联社/东方财富），
改为从已抓取、分类、评级的利好新闻数据库中读取数据，减少噪音。

双通道模式：
1. HTTP API（优先）: 调用 starweb.cpolar.io/api/news/query
2. SQLite 直接读取（回退）: API 不可用时直接连接本地 news.db

数据库索引利用：
- 个股新闻: code 参数利用 idx_news_code 索引精确查询
- 宏观快讯: date 参数利用 idx_news_date 索引按天查询
- 高星级优先: 客户端按 stars 排序，优先展示重磅利好

用法:
    from tradingagents.dataflows.local_news_api import (
        get_local_news_api,
        get_local_global_news_api,
    )
    news = get_local_news_api("603023", "2026-06-19", "2026-06-26")
    global_news = get_local_global_news_api("2026-06-26", look_back_days=7, limit=10)
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import requests

logger = logging.getLogger(__name__)

# API 基础地址（通过 cpolar 隧道暴露的本地 Flask 服务）
_BASE_URL = "https://starweb.cpolar.io"
_NEWS_QUERY = f"{_BASE_URL}/api/news/query"
_NEWS_DAILY = f"{_BASE_URL}/api/news/daily"
_NEWS_STATS = f"{_BASE_URL}/api/news/stats"

# 请求超时
_REQUEST_TIMEOUT = 10  # 秒

# 本地 SQLite 回退路径（API 不可用时使用）
# 优先级：环境变量 > 本模块同目录 > ~/gupiao/sql_db/
_DEFAULT_DB = Path(__file__).resolve().parent / "news.db"
_LOCAL_DB_PATH = os.environ.get(
    "TRADINGAGENTS_NEWS_DB_PATH",
    str(_DEFAULT_DB),
)


def _extract_code(ticker: str) -> str:
    """从 ticker 提取 6 位纯数字代码。603023.SH → 603023"""
    raw = (ticker or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        if raw.endswith(suffix):
            raw = raw[:-3]
            break
    return raw


def _call_api(endpoint: str, params: dict) -> dict | None:
    """调用 starweb API，返回 JSON dict 或 None（失败时）。"""
    try:
        resp = requests.get(endpoint, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.debug("新闻 API 不可用: %s", e)
        return None
    except ValueError as e:
        logger.debug("新闻 API 返回非 JSON: %s", e)
        return None


# ── SQLite 直接读取回退层 ──

def _sqlite_query(date=None, code=None, category=None, keyword=None,
                  limit=50, offset=0, order_by='date DESC'):
    """直接查询本地 news.db（绕过 HTTP API）。

    与 starweb news_db.query_news() 签名和返回格式一致。
    """
    db_path = Path(_LOCAL_DB_PATH)
    if not db_path.exists():
        return [], 0

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    where = []
    params = []

    if date:
        where.append("date = ?")
        params.append(date)
    if code:
        where.append("code = ?")
        params.append(code)
    if category:
        where.append("category = ?")
        params.append(category)
    if keyword and len(keyword) >= 2:
        like = f"%{keyword}%"
        where.append("(title LIKE ? OR stock_name LIKE ? OR content LIKE ? OR code = ?)")
        params.extend([like, like, like, keyword])

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=TRUE")
    conn.row_factory = sqlite3.Row

    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM news {where_clause}", params
        ).fetchone()[0]

        sql = f"""
        SELECT id, date, code, stock_name, category, title, summary,
               stars, rating, source, url, cap_yi, content, file_path, created_at
        FROM news {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """
        rows = [dict(r) for r in conn.execute(sql, params + [limit, offset]).fetchall()]
        return rows, total
    finally:
        conn.close()


# ── 统一查询入口（API 优先，SQLite 回退）──

def _query_news(date=None, code=None, category=None, keyword=None,
                limit=50, offset=0, order_by='date DESC'):
    """查询新闻：先尝试 HTTP API，失败时回退到直接 SQLite。"""
    global _last_source
    params = {
        "limit": limit,
        "offset": offset,
    }
    if date:
        params["date"] = date
    if code:
        params["code"] = code
    if category:
        params["category"] = category
    if keyword:
        params["q"] = keyword

    # 尝试 HTTP API
    data = _call_api(_NEWS_QUERY, params)
    if data is not None:
        _last_source = "api"
        items = data.get("items", [])
        total = data.get("total", len(items))
        return items, total

    # 回退到本地 SQLite
    _last_source = "sqlite"
    logger.info("API 不可用，回退到本地 SQLite: %s", _LOCAL_DB_PATH)
    return _sqlite_query(
        date=date, code=code, category=category, keyword=keyword,
        limit=limit, offset=offset, order_by=order_by,
    )


def _star_count(item: dict) -> int:
    """返回新闻的星级数量，用于排序。"""
    stars = item.get("stars", "") or ""
    return len(stars) if isinstance(stars, str) else 0


def _format_news_item(item: dict, index: int = 0) -> str:
    """将 API 返回的单条新闻格式化为 markdown 段落。"""
    lines = []
    title = item.get("title", "无标题") or "无标题"
    category = item.get("category", "")
    stars = item.get("stars", "")
    rating = item.get("rating", "")
    source = item.get("source", "")
    url = item.get("url", "")
    summary = item.get("summary", "")
    stock_name = item.get("stock_name", "")

    prefix = f"### {index}. " if index > 0 else "### "
    cat_label = f"【{category}】" if category else ""
    name_label = f" {stock_name}" if stock_name else ""
    lines.append(f"{prefix}{cat_label}{name_label} — {title}")

    if stars or rating:
        rating_str = f"{stars} {rating}".strip()
        lines.append(f"评级: {rating_str}")

    if summary and summary != title[:80]:
        lines.append(f"> {summary[:200]}")

    date = item.get("date", "")
    meta_parts = []
    if source:
        meta_parts.append(f"来源: {source}")
    if date:
        meta_parts.append(f"日期: {date}")
    if meta_parts:
        lines.append(f"- {'  |  '.join(meta_parts)}")

    if url:
        lines.append(f"- 链接: {url}")

    lines.append("")
    return "\n".join(lines)


def get_local_news_api(
    ticker: Annotated[str, "A股代码"],
    start_date: Annotated[str, "开始日期"],
    end_date: Annotated[str, "结束日期"],
) -> str:
    """从本地 news.db 获取 A 股个股新闻。

    利用 idx_news_code 索引按股票代码精确查询，
    客户端按日期范围过滤并依星级排序。
    """
    code = _extract_code(ticker)
    if not code:
        return f"# {ticker} 个股新闻\n无法解析股票代码\n"

    items, total = _query_news(code=code, limit=30, order_by="stars DESC, date DESC")

    # 按日期过滤 + 按星级排序
    filtered = []
    for item in items:
        item_date = item.get("date", "")
        if item_date and start_date <= item_date <= end_date:
            filtered.append(item)
        elif not item_date:
            filtered.append(item)

    filtered.sort(key=lambda x: (_star_count(x), x.get("date", "")), reverse=True)

    if not filtered:
        return (
            f"# {ticker} ({code}) 个股新闻\n"
            f"# 共 0 条（匹配 {total} 条，日期过滤后 0 条）\n"
            f"# 时间范围: {start_date} ~ {end_date}\n"
        )

    source_label = _source_label()
    lines = [
        f"# {ticker} ({code}) 个股新闻",
        f"# 共 {len(filtered)} 条（按星级排序，高星优先）",
        f"# 时间范围: {start_date} ~ {end_date}",
        f"# {source_label}",
        "",
    ]
    for i, item in enumerate(filtered, 1):
        lines.append(_format_news_item(item, i))

    return "\n".join(lines)


def get_local_global_news_api(
    curr_date: Annotated[str, "当前日期"],
    look_back_days: Annotated[int, "回顾天数"] = 7,
    limit: Annotated[int, "最大条数"] = 15,
) -> str:
    """宏观财经快讯 — 当前无可用宏观数据源。

    news.db 存储的是 A 股个股利好公告（增持/分红/定增等），
    不是宏观新闻（CPI/GDP/利率等）。直接返回空哨兵值，
    避免用无关个股公告填充 prompt 造成噪音。
    """
    return (
        "# 宏观财经快讯\n"
        "# 暂无宏观数据\n"
        "# news.db 仅包含个股利好公告，无宏观/利率/CPI/GDP 等数据。\n"
        "# 请专注于个股层面的新闻和基本面分析。\n"
    )


# 追踪最近一次查询实际使用的数据源
_last_source = "unknown"


def _source_label() -> str:
    """返回数据来源标签，反映实际使用的通道。"""
    if _last_source == "api":
        return "数据来源: starweb.cpolar.io (HTTP API)"
    if _last_source == "sqlite":
        return "数据来源: 本地 news.db (SQLite 回退)"
    return "数据来源: starweb.cpolar.io"


# ── 自检 ──
if __name__ == "__main__":
    print("=== local_news_api 自检 ===\n")

    # 1. 个股新闻
    print(">>> 个股新闻 (603023):")
    result = get_local_news_api("603023", "2026-06-19", "2026-06-26")
    print(result[:500])
    print()

    # 2. 宏观快讯
    print(">>> 宏观快讯 (近3天):")
    result = get_local_global_news_api("2026-06-26", look_back_days=3, limit=5)
    print(result[:500])
