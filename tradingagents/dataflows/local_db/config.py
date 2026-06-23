"""本地数据库 HTTP API 配置

环境变量:
    TRADINGAGENTS_LOCAL_DB_URL: API 根地址，默认 http://starweb.cpolar.io
"""

import os
import requests
import logging
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)

LOCAL_DB_URL = os.getenv(
    "TRADINGAGENTS_LOCAL_DB_URL",
    "http://starweb.cpolar.io"
).rstrip("/")

DB_STOCK = "stock"
DB_FINANCE = "stock_finance"
DB_MINUTE = "stock_minute"

_session = requests.Session()
_session.headers.update({
    "User-Agent": "TradingAgents-LocalDB/1.0",
    "Accept": "application/json",
})


def query_db(sql: str, db: str = "stock", limit: int = 10000, timeout: int = 30) -> Dict[str, Any]:
    """执行只读 SQL 查询。"""
    url = f"{LOCAL_DB_URL}/api/query"
    try:
        resp = _session.post(url, json={"db": db, "sql": sql, "limit": limit}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            logger.warning("DB query error: %s (db=%s, sql=%s...)", data["error"], db, sql[:120])
        return data
    except requests.RequestException as e:
        logger.error("DB query failed: %s (db=%s)", e, db)
        return {"error": str(e), "columns": [], "rows": [], "row_count": 0}


def query_dataframe(sql: str, db: str = "stock", **kwargs) -> "pd.DataFrame":
    """执行查询并返回 pandas DataFrame。"""
    result = query_db(sql, db=db, **kwargs)
    if "error" in result and not result.get("rows"):
        return pd.DataFrame()
    return pd.DataFrame(result.get("rows", []), columns=result.get("columns", []))


def _extract_code(symbol: str) -> int:
    """从标准代码提取整数 code。'600000.SH' -> 600000, '000001.SZ' -> 1"""
    raw = (symbol or "").strip()
    for suffix in (".SH", ".SZ", ".BJ"):
        if raw.upper().endswith(suffix):
            raw = raw[:-3]
            break
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


def _code_to_symbol(code: int, market: str = None) -> str:
    """整数 code -> 标准A股代码。1 -> 000001.SZ, 600000 -> 600000.SH"""
    code_str = str(code).zfill(6)
    if market:
        return f"{code_str}.{market}"
    if code_str.startswith(("60", "68")):
        return f"{code_str}.SH"
    elif code_str.startswith(("00", "30")):
        return f"{code_str}.SZ"
    elif code_str.startswith(("83", "87", "92")):
        return f"{code_str}.BJ"
    return f"{code_str}.SZ"
