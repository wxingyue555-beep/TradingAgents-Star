"""A股新闻聚合 — 新浪财经 + 财联社 + 东方财富（无API Key，公开接口）"""
from __future__ import annotations
import re, json, logging
from datetime import datetime, timedelta
from typing import Annotated
import requests
import re
from tradingagents.dataflows.local_db.config import _extract_code

logger = logging.getLogger(__name__)
_S = requests.Session()
_S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
})
_S.timeout = 8

# ── 新浪财经新闻（可用于个股搜索 + 宏观）──
SINA_ROLL = "https://feed.mix.sina.com.cn/api/roll/get"
SINA_PARAMS = {"pageid": "153", "lid": "2509", "num": "30", "versionNumber": "1.2.4", "encode": "utf-8"}

# ── 财联社电报 ──
CLS_URL = "https://www.cls.cn/nodeapi/telegraphList"

# ── 东方财富个股公告 ──
EM_ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"


def _fetch_sina_news(keyword: str = "", limit: int = 15) -> list[dict]:
    """从新浪财经拉取新闻列表。keyword不为空时过滤标题。"""
    results = []
    try:
        resp = _S.get(SINA_ROLL, params=SINA_PARAMS)
        data = resp.json()
        items = data.get("result", {}).get("data", [])
        for item in items:
            title = item.get("title", "")
            if keyword and keyword not in title:
                continue
            results.append({
                "title": title,
                "source": "新浪财经",
                "url": item.get("url", ""),
                "time": item.get("ctime", ""),
                "intro": item.get("intro", ""),
            })
            if len(results) >= limit:
                break
    except Exception as e:
        logger.warning("Sina news fetch failed: %s", e)
    return results


def _fetch_cls_telegraph(limit: int = 10) -> list[dict]:
    """财联社电报 — 实时快讯。"""
    results = []
    try:
        resp = _S.post(CLS_URL, json={"app": "CailianpressWeb", "os": "web", "sv": "8.4.6", "sign": ""})
        data = resp.json()
        items = data.get("data", {}).get("roll_data", []) or data.get("data", [])
        for item in items[:limit]:
            results.append({
                "title": item.get("title", "") or item.get("content", "")[:100],
                "source": "财联社",
                "url": f"https://www.cls.cn/detail/{item.get('id', '')}",
                "time": str(item.get("ctime", "") or item.get("modified_time", "")),
                "intro": item.get("content", "")[:200] if item.get("content") else "",
            })
    except Exception as e:
        logger.warning("CLS telegraph failed: %s", e)
    return results


def _fetch_em_announcements(code: str, limit: int = 5) -> list[dict]:
    """东方财富个股公告。"""
    results = []
    market = "SH" if code.startswith(("60", "68")) else "SZ"
    stock_list = f"{code},{market}"
    try:
        resp = _S.get(EM_ANN_URL, params={"page_size": limit, "page_index": 1, "stock_list": stock_list, "srcode": code})
        data = resp.json()
        items = data.get("data", {}).get("list", [])
        for item in items:
            cols = item.get("columns", [])
            col_name = cols[0].get("column_name", "") if cols else ""
            title = f"[{col_name}] {item.get('title_cn', '') or item.get('notice_title', '')}"
            results.append({
                "title": title,
                "source": "东方财富公告",
                "url": f"https://data.eastmoney.com/notices/detail/{code}/{item.get('art_code', '')}.html",
                "time": item.get("notice_date", "") or item.get("display_time", "")[:10],
                "intro": "",
            })
    except Exception as e:
        logger.warning("EM announcements failed: %s", e)
    return results


def _search_news(keyword: str, limit: int = 15) -> list[dict]:
    """综合搜索：新浪 + 公告。"""
    results = _fetch_sina_news(keyword, limit)
    code = _extract_code(keyword)
    if code > 0:
        results += _fetch_em_announcements(str(code), 5)
    return sorted(results, key=lambda x: str(x.get("time", "")), reverse=True)[:limit]


def _validate_news_time(time_str: str) -> tuple[str, bool]:
    """Validate and clean a news timestamp. Returns (cleaned_str, is_valid)."""
    if not time_str or not str(time_str).strip():
        return "", False
    now = datetime.now()
    # Try common timestamp formats (Unix ms)
    try:
        ts = int(str(time_str).strip())
        if ts > 1e12:  # milliseconds
            dt = datetime.fromtimestamp(ts / 1000)
        elif ts > 1e9:  # seconds
            dt = datetime.fromtimestamp(ts)
        else:
            return str(time_str), False
    except (ValueError, OSError):
        # Try date string formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(time_str)[:19], fmt)
                break
            except ValueError:
                continue
        else:
            # Can't parse — return as-is, don't filter
            return str(time_str), True
    # Future dates (more than 1 day ahead = data error)
    if dt > now + timedelta(days=1):
        return str(time_str), False
    # Too old (before 2024-01-01 = likely timestamp error)
    if dt < datetime(2024, 1, 1):
        return str(time_str), False
    return dt.strftime("%Y-%m-%d %H:%M"), True


def _format_news(news_list: list[dict], title: str) -> str:
    if not news_list:
        return f"# {title}\n暂无相关新闻数据\n"
    valid_news = []
    skipped = 0
    for n in news_list:
        clean_time, is_valid = _validate_news_time(n.get("time", ""))
        if not is_valid:
            skipped += 1
            continue
        n["_clean_time"] = clean_time
        valid_news.append(n)
    lines = [f"# {title}", f"# 共 {len(valid_news)} 条" +
             (f"（已过滤 {skipped} 条异常时间戳）" if skipped else ""), ""]
    for i, n in enumerate(valid_news, 1):
        lines.append(f"### {i}. {n['title']}")
        if n.get("intro"):
            lines.append(f"> {n['intro'][:200]}")
        lines.append(f"- 来源: {n.get('source', '')}  |  时间: {n.get('_clean_time', n.get('time', ''))}")
        if n.get("url"):
            lines.append(f"- 链接: {n['url']}")
        lines.append("")
    return "\n".join(lines)




# ── 本地新闻目录 ──
def _read_local_news_dir(news_dir: str, keyword: str = "", limit: int = 15) -> list[dict]:
    """从指定目录读取新闻文件。"""
    from pathlib import Path
    import os
    results = []
    dir_path = Path(news_dir).expanduser()
    if not dir_path.exists():
        return results
    for f in sorted(list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md")), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").strip()
            if keyword and keyword not in text:
                continue
            lines = text.split("\n")
            # Strip markdown headings from title
            # Strip markdown headings from title
            title = ""
            for l in lines:
                t = l.lstrip("#").strip()
                if t:
                    title = t[:200]
                    break
            if not title:
                title = f.stem
            title = re.sub(r"^#+\s*", "", title)
            results.append({
                "title": title[:200],
                "source": f"本地: {f.name}",
                "url": str(f),
                "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "intro": "\n".join(lines[1:4])[:300] if len(lines) > 1 else "",
            })
            if len(results) >= limit:
                break
        except Exception:
            pass
    return results


def get_china_stock_news(
    ticker: Annotated[str, "A股代码"],
    start_date: Annotated[str, "开始日期"],
    end_date: Annotated[str, "结束日期"],
) -> str:
    """获取A股个股新闻。优先本地目录，fallback在线源。"""
    import os
    code = _extract_code(ticker)
    keyword = str(code) if code > 0 else ticker
    
    # Check for local news dir
    local_dir = os.environ.get("TRADINGAGENTS_LOCAL_NEWS_DIR", "")
    local_news = _read_local_news_dir(local_dir, keyword, 10) if local_dir else []
    
    online_news = _search_news(keyword, 10)
    if not online_news and len(str(code)) == 6:
        online_news = _fetch_sina_news(str(code), 10)
    
    all_news = local_news + online_news
    return _format_news(all_news[:15], f"{ticker} 个股新闻")


def get_china_global_news(
    curr_date: Annotated[str, "当前日期"],
    look_back_days: Annotated[int, "回顾天数"] = 3,
    limit: Annotated[int, "最大条数"] = 15,
) -> str:
    """获取宏观财经快讯。"""
    import os
    local_dir = os.environ.get("TRADINGAGENTS_LOCAL_NEWS_DIR", "")
    local_news = _read_local_news_dir(local_dir, "", 8) if local_dir else []
    
    cls_news = _fetch_cls_telegraph(8)
    sina_news = _fetch_sina_news("", 8)
    all_news = local_news + cls_news + sina_news
    all_news = sorted(all_news, key=lambda x: str(x.get("time", "")), reverse=True)[:limit]
    return _format_news(all_news, "宏观财经快讯")
