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
    # price: 元/股, volume: 手 (1手=100股)
    # amount = price * volume * 100 → 元
    for r in rows:
        p = float(r.get("price",0) or 0)
        v = float(r.get("volume",0) or 0)
        r["amount"] = p * v * 100  # 元
    amounts = sorted([r["amount"] for r in rows if r["amount"]>0])
    if not amounts: return f"No valid tick data for '{symbol}'"
    med = amounts[len(amounts)//2]
    def classify(amt):
        if amt > med*8: return "超大单"
        if amt > med*3: return "大单"
        if amt > med*0.5: return "中单"
        return "小单"
    daily = {}
    # Also track total turnover per day for sanity checks
    daily_turnover = {}
    for r in rows:
        d = r["trade_date"]; otype = classify(r["amount"])
        net = r["amount"] if r.get("direction","B")=="B" else -r["amount"]
        if d not in daily:
            daily[d] = {"超大单":0,"大单":0,"中单":0,"小单":0}
            daily_turnover[d] = 0.0
        daily[d][otype] = daily[d].get(otype,0) + net
        daily_turnover[d] += abs(r["amount"])
    for d, flows in daily.items():
        flows["主力净流入"] = flows.get("超大单",0) + flows.get("大单",0)
        # Sanity: 主力净流入绝对值不应超过当日总成交额
        total = daily_turnover.get(d, 1)
        if abs(flows["主力净流入"]) > total * 1.01:
            flows["_sanity_warning"] = True
        else:
            flows["_sanity_warning"] = False
    sd = sorted(daily.keys())
    med_hdr = f"超大单>{med*8:.0f}元, 大单>{med*3:.0f}元, 中单>{med*0.5:.0f}元"
    hdr = (f"# 资金流向 for {symbol} 从 {start_date} 到 {end_date}\n"
           f"# 来源: tick_trade 自适应阈值自算\n"
           f"# 计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
           f"# ⚠️ CRITICAL: 所有金额单位为 万元（人民币），1万元=10,000元。合计X万元=X/10000亿。严禁误读为亿元。\n"
           f"# 自适应阈值: {med_hdr}\n"
           f"# 总笔数: {len(rows)}{' (已截断)' if truncated else ''}\n"
           f"# ⚠️ 注意: 资金流源自 tick_trade 分笔表，与 daily_kline 的日成交量统计口径不同，数值不可直接对比。\n"
           f"# 查询耗时: {(datetime.now()-t0).total_seconds():.1f}s\n\n")
    lines = [hdr, "Date,主力净流入(万元),小单净流入(万元),中单净流入(万元),大单净流入(万元),超大单净流入(万元)"]
    total_inflow = 0.0; total_outflow = 0.0
    inflow_days = 0; outflow_days = 0
    for d in sd:
        f = daily[d]; ds = str(d)
        if len(ds)==8: ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
        warn = " ⚠️" if f.get("_sanity_warning") else ""
        net = f['主力净流入'] / 1e4  # 万元
        if net > 0: total_inflow += net; inflow_days += 1
        elif net < 0: total_outflow += abs(net); outflow_days += 1
        lines.append(f"{ds},{net:.2f},{f['小单']/1e4:.2f},{f['中单']/1e4:.2f},{f['大单']/1e4:.2f},{f['超大单']/1e4:.2f}{warn}")
    # Statistical summary
    total_days = inflow_days + outflow_days
    lines.append("")
    lines.append("# === 统计摘要 ===")
    lines.append(f"# 分析天数: {total_days} (流入 {inflow_days} 天, 流出 {outflow_days} 天)")
    if total_days > 0:
        outflow_ratio = outflow_days / total_days
        lines.append(f"# 流出天数占比: {outflow_ratio:.1%}")
        if outflow_ratio >= 0.70:
            lines.append(f"# ⚠️ 流出天数显著偏高 ({outflow_ratio:.0%}), 远大于随机50%基线, 主力持续卖出信号强烈")
        elif outflow_ratio >= 0.55:
            lines.append(f"# 流出天数略多 ({outflow_ratio:.0%}), 主力偏空但非极端")
        elif outflow_ratio <= 0.45:
            lines.append(f"# 流入天数占优 ({1-outflow_ratio:.0%}), 主力偏多")
    if inflow_days > 0:
        lines.append(f"# 流入日平均: +{total_inflow/inflow_days:.2f} 万元")
    if outflow_days > 0:
        lines.append(f"# 流出日平均: -{total_outflow/outflow_days:.2f} 万元")
    if total_days > 0:
        lines.append(f"# 全周期净额: {(total_inflow-total_outflow):.2f} 万元")
    return "\n".join(lines)
