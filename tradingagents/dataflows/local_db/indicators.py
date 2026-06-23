"""技术指标 - 基于 daily_kline 本地计算 SMA/EMA/MACD/RSI/BOLL/KDJ"""
from datetime import datetime, timedelta
from typing import Annotated
import pandas as pd
from .config import query_dataframe, _extract_code

def get_local_indicators(symbol: Annotated[str,"A股代码"], indicator: Annotated[str,"指标类型"], curr_date: Annotated[str,"当前日期 yyyy-mm-dd"], look_back_days: Annotated[int,"回顾天数"]) -> str:
    code = _extract_code(symbol)
    if code == 0: return f"Error: 无法解析股票代码 '{symbol}'"
    end_dt = datetime.strptime(curr_date,"%Y-%m-%d"); start_dt = end_dt - timedelta(days=look_back_days*3)
    si, ei = int(start_dt.strftime("%Y%m%d")), int(end_dt.strftime("%Y%m%d"))
    df = query_dataframe(f"SELECT trade_date,open,high,low,close,volume FROM daily_kline WHERE code={code} AND trade_date BETWEEN {si} AND {ei} ORDER BY trade_date", db="stock")
    if df.empty: return f"No data for {symbol}"
    for c in ["open","high","low","close"]:
        if c in df.columns: df[c] = df[c].astype(float)/100.0
    df["Date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
        # Map common indicator names to local_db supported types
    name_map = {
        'close_50_sma': 'sma', 'close_200_sma': 'sma', 'close_10_ema': 'ema',
        'close_20_ema': 'ema', 'close_50_ema': 'ema',
        'sma_50': 'sma', 'sma_200': 'sma', 'ema_10': 'ema', 'ema_20': 'ema',
        'macd_line': 'macd', 'macds': 'macd', 'macdh': 'macd',
        'rsi_6': 'rsi', 'rsi_12': 'rsi', 'rsi_24': 'rsi',
        'boll_ub': 'boll', 'boll_lb': 'boll', 'bollinger': 'boll',
        'atr': 'sma', 'vwma': 'sma', 'volume': 'sma',
        'close_10_sma': 'sma', 'close_20_sma': 'sma',
    }
    ind = indicator.lower().strip()
    ind = name_map.get(ind, ind)
    lines = []
    if ind in ("sma","ma"):
        for w in [5,10,20,60]:
            if len(df)>=w:
                s = df["close"].rolling(w).mean().iloc[-1]
                if pd.notna(s): lines.append(f"SMA {w}: {s:.2f}")
    elif ind == "ema":
        for w in [5,10,20,60]:
            if len(df)>=w:
                s = df["close"].ewm(span=w, adjust=False).mean().iloc[-1]
                if pd.notna(s): lines.append(f"EMA {w}: {s:.2f}")
    elif ind == "macd":
        e12 = df["close"].ewm(span=12,adjust=False).mean(); e26 = df["close"].ewm(span=26,adjust=False).mean()
        m = e12-e26; sig = m.ewm(span=9,adjust=False).mean(); hist = m-sig
        if len(df)>0: lines.extend([f"MACD: {m.iloc[-1]:.2f}",f"Signal: {sig.iloc[-1]:.2f}",f"Histogram: {hist.iloc[-1]:.2f}"])
    elif ind == "rsi":
        for w in [6,12,24]:
            if len(df)>=w+1:
                d = df["close"].diff(); g = d.where(d>0,0).rolling(w).mean(); l = (-d.where(d<0,0)).rolling(w).mean()
                rs = g/l; rsi_val = 100-(100/(1+rs))
                if pd.notna(rsi_val.iloc[-1]): lines.append(f"RSI {w}: {rsi_val.iloc[-1]:.2f}")
    elif ind == "boll":
        w=20
        if len(df)>=w:
            sma = df["close"].rolling(w).mean(); std = df["close"].rolling(w).std()
            if pd.notna(sma.iloc[-1]): lines.extend([f"BOLL Mid({w}): {sma.iloc[-1]:.2f}",f"BOLL Upper: {(sma+std*2).iloc[-1]:.2f}",f"BOLL Lower: {(sma-std*2).iloc[-1]:.2f}"])
    elif ind == "kdj":
        w=9
        if len(df)>=w:
            ln = df["low"].rolling(w).min(); hn = df["high"].rolling(w).max()
            rsv = (df["close"]-ln)/(hn-ln)*100; k = rsv.ewm(com=2,adjust=False).mean()
            d = k.ewm(com=2,adjust=False).mean(); j = 3*k-2*d
            if pd.notna(k.iloc[-1]): lines.extend([f"K: {k.iloc[-1]:.2f}",f"D: {d.iloc[-1]:.2f}",f"J: {j.iloc[-1]:.2f}"])
    result = f"# {symbol} 技术指标 - {indicator.upper()}\n# 回顾: {start_dt.strftime('%Y-%m-%d')} ~ {curr_date}\n# 来源: 本地通达信数据库\n\n"
    return result + ("\n".join(lines) if lines else f"指标 {indicator} 暂不支持")
