"""基本面+估值 - financial表 + daily_kline最新价计算PE/PB/市值"""
from datetime import datetime
from typing import Annotated
from .config import query_db, _extract_code

def _get_latest_price(code): 
    data = query_db(f"SELECT close FROM daily_kline WHERE code={code} ORDER BY trade_date DESC LIMIT 1", db="stock", limit=1)
    rows = data.get("rows",[]); return rows[0]["close"]/100.0 if rows and rows[0].get("close") else 0

def _get_latest_financial(code):
    data = query_db(f"SELECT * FROM financial WHERE code={code} ORDER BY report_date DESC LIMIT 1", db="stock_finance", limit=1)
    rows = data.get("rows",[]); return rows[0] if rows else {}

def _fmt_amount(val):
    if val is None: return "N/A"
    try:
        v = float(val)
        if abs(v)>=1e8: return f"{v/1e8:,.2f} 亿"
        elif abs(v)>=1e4: return f"{v/1e4:,.2f} 万"
        return f"{v:,.2f}"
    except: return str(val) if val else "N/A"

def _fmt_pct(val):
    if val is None: return "N/A"
    try: return f"{float(val):.2f}%"
    except: return str(val) if val else "N/A"

def get_local_fundamentals(symbol: Annotated[str,"A股代码"], curr_date: Annotated[str,None]=None) -> str:
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    price = _get_latest_price(code); fin = _get_latest_financial(code)
    if not fin: return f"No fundamental data found for '{symbol}'."
    rd = str(fin.get("report_date","N/A"))
    if len(rd)==8: rd = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}"
    ts = fin.get("总股本") or 0; eps = fin.get("基本每股收益") or 0; bps = fin.get("每股净资产") or 0
    tmc = price * (float(ts)) if ts else 0
    pe = price/eps if eps and float(eps)>0 else None
    pb = price/bps if bps and float(bps)>0 else None
    r = f"# {symbol} 基本面数据\n# 数据来源: 本地通达信数据库\n# 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n# 财务报告期: {rd}\n\n"
    r += f"## 公司信息\n- 股票代码: {symbol}\n- 总股本: {_fmt_amount(float(ts))} 股\n\n"
    r += f"## 估值指标\n- 最新价: {price}\n- 总市值: {_fmt_amount(tmc)}\n"
    r += f"- 市盈率(动态): {pe:.2f}\n" if pe else "- 市盈率(动态): N/A\n"
    r += f"- 市净率: {pb:.2f}\n\n" if pb else "- 市净率: N/A\n\n"
    r += f"## 盈利能力\n- EPS: {eps} 元\n- BPS: {bps} 元\n- ROE: {_fmt_pct(fin.get('净资产收益率')or 0)}\n"
    r += f"- 毛利率: {_fmt_pct(fin.get('销售毛利率(%)')or 0)}\n\n"
    r += f"## 成长性\n- 营收增长率: {_fmt_pct(fin.get('营业收入增长率')or 0)}\n"
    r += f"- 净利润增长率: {_fmt_pct(fin.get('净利润增长率')or 0)}\n\n"
    r += f"## 财务健康\n- 资产负债率: {_fmt_pct(fin.get('资产负债率(%)')or 0)}\n"
    r += f"- 流动比率: {fin.get('流动比率') or 'N/A'}\n- 速动比率: {fin.get('速动比率') or 'N/A'}\n"
    r += f"- 总资产: {_fmt_amount(fin.get('资产总计')or 0)}\n- 净资产: {_fmt_amount(fin.get('所有者权益（或股东权益）合计')or 0)}\n\n"
    r += f"## 最新业绩\n- 营收: {_fmt_amount(fin.get('营业收入') or fin.get('其中：营业收入') or 0)}\n"
    r += f"- 营业利润: {_fmt_amount(fin.get('三、营业利润')or 0)}\n"
    r += f"- 归母净利润: {_fmt_amount(fin.get('归属于母公司所有者的净利润')or 0)}\n"
    r += f"- 经营现金流: {_fmt_amount(fin.get('经营活动产生的现金流量净额')or 0)}\n"
    return r
