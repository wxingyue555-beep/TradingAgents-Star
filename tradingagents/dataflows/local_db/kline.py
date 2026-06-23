"""日K线数据查询 - stock.db daily_kline 表。价格x100还原，输出CSV。"""
from datetime import datetime
from typing import Annotated
from .config import query_db, _extract_code

def _safe_div(val, divisor):
    if val is None: return 0
    if isinstance(val, (int, float)): return round(val / divisor, 2)
    return 0

def _format_kline_result(data, symbol, start_date, end_date):
    rows = data.get("rows", [])
    if not rows:
        return f"No data found for '{symbol}' between {start_date} and {end_date}"
    header = (
        f"# A股数据 for {symbol} 从 {start_date} 到 {end_date}\n"
        f"# 股票代码: {symbol}\n# 记录数: {len(rows)}\n"
        f"# 数据来源: 本地通达信数据库 (stock.db via HTTP API)\n"
        f"# 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    lines = [header, "Date,Open,High,Low,Close,Volume,Amount"]
    for row in rows:
        dv = str(row.get("trade_date", ""))
        if len(dv) == 8: dv = f"{dv[:4]}-{dv[4:6]}-{dv[6:8]}"
        lines.append(f"{dv},{_safe_div(row.get('open',0),100)},{_safe_div(row.get('high',0),100)},{_safe_div(row.get('low',0),100)},{_safe_div(row.get('close',0),100)},{int(row.get('volume',0))},{row.get('amount',0)}")
    return "\n".join(lines)

def get_local_stock_data(symbol: Annotated[str,"A股代码"], start_date: Annotated[str,"开始日期 yyyy-mm-dd"], end_date: Annotated[str,"结束日期 yyyy-mm-dd"]) -> str:
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    si, ei = int(start_date.replace("-","")), int(end_date.replace("-",""))
    data = query_db(f"SELECT code,trade_date,open,high,low,close,amount,volume FROM daily_kline WHERE code={code} AND trade_date BETWEEN {si} AND {ei} ORDER BY trade_date", db="stock", limit=10000)
    if "error" in data and not data.get("rows"): return f"Error fetching kline data for {symbol}: {data['error']}"
    return _format_kline_result(data, symbol, start_date, end_date)

def get_local_stock_quote(symbol: Annotated[str,"A股代码"]) -> str:
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    data = query_db(f"SELECT code,trade_date,open,high,low,close,amount,volume FROM daily_kline WHERE code={code} ORDER BY trade_date DESC LIMIT 1", db="stock", limit=1)
    rows = data.get("rows",[])
    if not rows: return f"No quote data found for '{symbol}'"
    r = rows[0]; ds = str(r.get("trade_date",""))
    if len(ds)==8: ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    return (f"# {symbol} 实时行情\n# 数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"代码: {symbol}\n日期: {ds}\n开盘: {_safe_div(r.get('open',0),100)}\n"
            f"最高: {_safe_div(r.get('high',0),100)}\n最低: {_safe_div(r.get('low',0),100)}\n"
            f"最新价: {_safe_div(r.get('close',0),100)}\n成交量: {int(r.get('volume',0))}\n成交额: {r.get('amount',0)}\n")


def get_local_kline_raw(symbol: str, start_date: str, end_date: str) -> list[float]:
    """Return a list of close prices (元) between start_date and end_date inclusive.
    
    Used by the reflection/alpha calculator as a yfinance-free replacement.
    Returns an empty list if no data is found.
    """
    code = _extract_code(symbol)
    if code == 0:
        return []
    si, ei = int(start_date.replace("-", "")), int(end_date.replace("-", ""))
    data = query_db(
        f"SELECT close FROM daily_kline WHERE code={code} AND trade_date BETWEEN {si} AND {ei} ORDER BY trade_date",
        db="stock", limit=100
    )
    rows = data.get("rows", [])
    return [row["close"] / 100.0 for row in rows if row.get("close")]
