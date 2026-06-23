"""三大财务报表 - stock_finance.db financial 表 (264字段)"""
from datetime import datetime
from typing import Annotated
from .config import query_db, _extract_code

BALANCE_HIGHLIGHT = [
    ("资产总计","总资产"),("负债合计","总负债"),("所有者权益（或股东权益）合计","股东权益"),
    ("流动资产合计","流动资产"),("非流动资产合计","非流动资产"),("流动负债合计","流动负债"),
    ("非流动负债合计","非流动负债"),("货币资金","货币资金"),("应收账款","应收账款"),
    ("存货","存货"),("应收票据","应收票据"),("未分配利润","未分配利润"),
    ("固定资产","固定资产"),("在建工程","在建工程"),("无形资产","无形资产"),
    ("商誉","商誉"),("短期借款","短期借款"),("长期借款","长期借款"),
]
INCOME_HIGHLIGHT = [
    ("营业收入","营业收入"),("其中：营业成本","营业成本"),("三、营业利润","营业利润"),
    ("四、利润总额","利润总额"),("五、净利润","净利润"),("归属于母公司所有者的净利润","归母净利润"),
    ("扣除非经常性损益后的净利润","扣非净利润"),("基本每股收益","基本每股收益"),
    ("销售费用","销售费用"),("管理费用","管理费用"),("财务费用","财务费用"),
    ("投资收益","投资收益"),("营业外收入","营业外收入"),
]
CASHFLOW_HIGHLIGHT = [
    ("经营活动产生的现金流量净额","经营活动现金流"),("投资活动产生的现金流量净额","投资活动现金流"),
    ("筹资活动产生的现金流量净额","筹资活动现金流"),("销售商品、提供劳务收到的现金","销售收到的现金"),
    ("购买商品、接受劳务支付的现金","采购支付的现金"),
    ("购建固定资产、无形资产和其他长期资产支付的现金","购建资产支付的现金"),
    ("期末现金及现金等价物余额","期末现金余额"),("期初现金及现金等价物余额","期初现金余额"),
]

def _fmt_amt(val):
    if val is None: return "N/A"
    try:
        v = float(val)
        if abs(v)>=1e8: return f"{v/1e8:,.2f} 亿"
        elif abs(v)>=1e4: return f"{v/1e4:,.2f} 万"
        return f"{v:,.2f}"
    except (ValueError,TypeError): return str(val) if val else "N/A"

def _fetch_and_format(symbol, highlight_fields, report_label):
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    data = query_db(f"SELECT * FROM financial WHERE code={code} ORDER BY report_date DESC LIMIT 4", db="stock_finance", limit=4)
    rows = data.get("rows",[])
    if not rows: return f"No {report_label} data found for '{symbol}'."
    lines = [f"# {symbol} {report_label}", f"# 数据来源: 本地通达信数据库 (stock_finance.db)",
             f"# 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"# 报告期数: {len(rows)}\n"]
    seen = set()
    for row in rows:
        rpt = str(row.get("report_date","N/A"))
        if len(rpt)==8: rpt = f"{rpt[:4]}-{rpt[4:6]}-{rpt[6:8]}"
        lines.append(f"## 报告期: {rpt}\n")
        for fk, fl in highlight_fields:
            if fl in seen and fk != fl: continue
            val = row.get(fk)
            if val is not None and val != "" and val != 0:
                seen.add(fl); lines.append(f"- {fl}: {_fmt_amt(val)}")
        lines.append(""); seen = set()
    return "\n".join(lines)

def get_local_balance_sheet(symbol: Annotated[str,"A股代码"], freq: Annotated[str,"annual/quarterly"]="quarterly", curr_date: Annotated[str,None]=None) -> str:
    return _fetch_and_format(symbol, BALANCE_HIGHLIGHT, "资产负债表")

def get_local_cashflow(symbol: Annotated[str,"A股代码"], freq: Annotated[str,"annual/quarterly"]="quarterly", curr_date: Annotated[str,None]=None) -> str:
    return _fetch_and_format(symbol, CASHFLOW_HIGHLIGHT, "现金流量表")

def get_local_income_statement(symbol: Annotated[str,"A股代码"], freq: Annotated[str,"annual/quarterly"]="quarterly", curr_date: Annotated[str,None]=None) -> str:
    return _fetch_and_format(symbol, INCOME_HIGHLIGHT, "利润表")
