"""股票搜索 - stock_basic 表"""
from typing import Annotated
from .config import query_db, _extract_code, _code_to_symbol

def search_local_stock(keyword: Annotated[str,"搜索关键词"]) -> str:
    kw = (keyword or "").strip()
    if not kw: return "请提供搜索关键词"
    code = _extract_code(kw)
    if code > 0:
        data = query_db(f"SELECT code,market,name FROM stock_basic WHERE code={code}", db="stock", limit=5)
        rows = data.get("rows",[])
        if rows: return _fmt(rows, keyword)
    if kw.isdigit():
        data = query_db(f"SELECT code,market,name FROM stock_basic WHERE CAST(code AS TEXT) LIKE '%{kw}%' LIMIT 20", db="stock", limit=20)
    else:
        data = query_db(f"SELECT code,market,name FROM stock_basic WHERE name LIKE '%{kw}%' LIMIT 20", db="stock", limit=20)
    rows = data.get("rows",[])
    return _fmt(rows, keyword) if rows else f"No search results for '{keyword}'"

def _fmt(rows, kw):
    r = f"# 搜索结果 for '{kw}'\n\n{'标准代码':<12} {'代码':<8} {'市场':<6} {'名称':<12}\n" + "-"*40 + "\n"
    for row in rows:
        sym = _code_to_symbol(row.get("code",0), row.get("market"))
        r += f"{sym:<12} {str(row.get('code','')):<8} {row.get('market','??'):<6} {(row.get('name') or 'N/A'):<12}\n"
    return r

def resolve_local_symbol(user_input: str) -> dict:
    raw = (user_input or "").strip()
    if not raw: return {"ok":False,"symbol":None,"name":None,"candidates":[],"message":"请输入股票代码"}
    code = _extract_code(raw)
    if code == 0: return {"ok":False,"symbol":None,"name":None,"candidates":[],"message":f"无法识别: {raw}"}
    data = query_db(f"SELECT code,market,name FROM stock_basic WHERE code={code}", db="stock", limit=1)
    rows = data.get("rows",[]); mkt = rows[0].get("market") if rows else None; nm = rows[0].get("name") if rows else None
    return {"ok":True,"symbol":_code_to_symbol(code,mkt),"name":nm,"candidates":[],"message":None}
