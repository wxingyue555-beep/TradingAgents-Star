"""资金流向 - 基于 tick_trade 分笔数据自适应阈值计算"""
from datetime import datetime
from typing import Annotated
from .config import query_db, _extract_code

def get_local_capital_flow(symbol: Annotated[str,"A股代码"], start_date: Annotated[str,"开始日期"], end_date: Annotated[str,"结束日期"]) -> str:
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    si, ei = int(start_date.replace("-","")), int(end_date.replace("-",""))
    t0 = datetime.now()
    data = query_db(f"SELECT trade_date,price,direction,volume FROM tick_trade WHERE code={code} AND trade_date BETWEEN {si} AND {ei} ORDER BY trade_date", db="stock", limit=100000)
    rows = data.get("rows",[]); truncated = data.get("truncated",False)
    if not rows: return f"No tick trade data found for '{symbol}'.\n提示: tick_trade 数据从 2026-06-01 开始。"
    for r in rows: r["amount"] = float(r.get("price",0) or 0) * float(r.get("volume",0) or 0) * 100
    amounts = sorted([r["amount"] for r in rows if r["amount"]>0])
    if not amounts: return f"No valid tick data for '{symbol}'"
    med = amounts[len(amounts)//2]
    def classify(amt):
        if amt > med*8: return "超大单"
        if amt > med*3: return "大单"
        if amt > med*0.5: return "中单"
        return "小单"
    daily = {}
    for r in rows:
        d = r["trade_date"]; otype = classify(r["amount"])
        net = r["amount"] if r.get("direction","B")=="B" else -r["amount"]
        if d not in daily: daily[d] = {"超大单":0,"大单":0,"中单":0,"小单":0}
        daily[d][otype] = daily[d].get(otype,0) + net
    for d, flows in daily.items(): flows["主力净流入"] = flows.get("超大单",0) + flows.get("大单",0)
    sd = sorted(daily.keys())
    hdr = (f"# 资金流向 for {symbol} 从 {start_date} 到 {end_date}\n"
           f"# 来源: tick_trade 自适应阈值自算\n# 计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
           f"# 自适应阈值: 超大单>{med*8:.0f}元, 大单>{med*3:.0f}元, 中单>{med*0.5:.0f}元\n"
           f"# 总笔数: {len(rows)}{' (已截断)' if truncated else ''}\n"
           f"# 查询耗时: {(datetime.now()-t0).total_seconds():.1f}s\n\n")
    lines = [hdr, "Date,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入"]
    for d in sd:
        f = daily[d]; ds = str(d)
        if len(ds)==8: ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
        lines.append(f"{ds},{f['主力净流入']:.0f},{f['小单']:.0f},{f['中单']:.0f},{f['大单']:.0f},{f['超大单']:.0f}")
    return "\n".join(lines)
