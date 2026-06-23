"""持仓股列表 - 从 ~/gupiao/data/ 目录自动发现"""
import os, re
from pathlib import Path
from typing import Dict, List, Optional
from .config import _code_to_symbol

_WATCHLIST_DIR = Path(os.getenv("TRADINGAGENTS_WATCHLIST_DIR", os.path.expanduser("~/gupiao/data")))
_DIRNAME_PATTERN = re.compile(r"(\d{6})$")
_EXCLUDE_DIRS = {"_template","memory",".git","__pycache__",".deepseek",".cache"}

def scan_watchlist() -> Dict[str, dict]:
    stocks = {}
    if not _WATCHLIST_DIR.exists(): return stocks
    for entry in sorted(_WATCHLIST_DIR.iterdir()):
        if not entry.is_dir() or entry.name in _EXCLUDE_DIRS: continue
        m = _DIRNAME_PATTERN.search(entry.name)
        if not m: continue
        code = m.group(1); name = entry.name.replace(code,"").strip().rstrip("-_ ")
        symbol = _code_to_symbol(int(code)); stocks[code] = {"name":name,"dirname":entry.name,"path":str(entry),"symbol":symbol}
    return stocks

def get_watchlist_symbols() -> List[str]:
    return sorted([v["symbol"] for v in scan_watchlist().values()])

def get_watchlist_options() -> List[tuple]:
    return sorted([(v["symbol"], f"{v['name']} ({v['symbol']})") for v in scan_watchlist().values()])

def resolve_to_symbol(query: str) -> Optional[str]:
    wl = scan_watchlist()
    q = query.strip()
    for code, info in wl.items():
        if q in (code, info["symbol"]) or q in info["name"]: return info["symbol"]
    return None
