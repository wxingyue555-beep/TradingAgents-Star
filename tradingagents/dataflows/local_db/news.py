"""本地新闻 - ~/gupiao/news/ 分类新闻库"""
import os, re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, List
from .config import _extract_code

_NEWS_DIR = Path(os.getenv("TRADINGAGENTS_LOCAL_NEWS_DIR", os.path.expanduser("~/gupiao/news")))

def _find_news_files(code: int, look_back_days: int = 7) -> List[Path]:
    files = []
    if not _NEWS_DIR.exists(): return files
    today = datetime.now()
    for d in range(look_back_days):
        day = today - timedelta(days=d); day_dir = _NEWS_DIR / day.strftime("%Y-%m-%d")
        if not day_dir.exists(): continue
        cp = f"_{code:06d}_" if code >= 100000 else f"_{code}_"
        for f in sorted(list(day_dir.glob("*.txt")) + list(day_dir.glob("*.md"))):
            if cp in f.name: files.append(f)
    return files

def _parse_news_file(fp: Path) -> dict:
    try: text = fp.read_text(encoding="utf-8").strip()
    except: return {}
    lines = text.split("\n"); result = {"file":fp.name,"date":"","category":"","code":"","name":"","title":"","source":"","stars":"","detail":""}
    stem = fp.stem; parts = stem.split("_",3)
    if len(parts)>=2: result["category"]=parts[0]; result["code"]=parts[1] if len(parts)>1 else ""
    if len(parts)>=3: result["date"]=parts[2]
    if lines:
        m = re.match(r"【(.+?)】(.+?)\((\d+)\)", lines[0])
        if m: result["category"]=m.group(1); result["name"]=m.group(2); result["code"]=m.group(3)
    for line in lines:
        if line.startswith("标题:"): result["title"]=line.replace("标题:","").strip()
        elif line.startswith("来源:"): result["source"]=line.replace("来源:","").strip()
        elif line.startswith("星级:"): result["stars"]=line.replace("星级:","").strip()
        elif line.startswith("详情:") or line.startswith("新闻日期:"): result["detail"]=line.split(":",1)[1].strip() if ":" in line else ""
    return result

def get_local_news(ticker: Annotated[str,"股票代码"], start_date: Annotated[str,"开始日期"], end_date: Annotated[str,"结束日期"]) -> str:
    code = _extract_code(ticker)
    if code == 0: return f"Error: 无法解析股票代码 '{ticker}'"
    try:
        sd = datetime.strptime(start_date,"%Y-%m-%d"); ed = datetime.strptime(end_date,"%Y-%m-%d")
        lb = max((ed-sd).days+7, 14)
    except: lb = 14
    files = _find_news_files(code, lb)
    if not files:
        for cd in _NEWS_DIR.iterdir():
            if not cd.is_dir(): continue
            for f in list(cd.glob("*.txt")) + list(cd.glob("*.md")):
                if f"_{code}_" in f.name or f"_{code:06d}_" in f.name: files.append(f)
    if not files: return f"# {ticker} 本地新闻\n# 未找到相关新闻 (代码: {code})\n# 新闻库: {_NEWS_DIR}\n"
    lines = [f"# {ticker} 本地新闻", f"# 来源: 本地新闻库 ({_NEWS_DIR})", f"# 匹配数: {len(files)}", f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]
    for fp in sorted(files, reverse=True)[:20]:
        n = _parse_news_file(fp)
        if not n: continue
        lines.append(f"## {n.get('category','未知')}: {n.get('title',fp.stem)}")
        if n.get('stars'): lines.append(f"星级: {n['stars']}")
        if n.get('source'): lines.append(f"来源: {n['source']}")
        if n.get('date'): lines.append(f"日期: {n['date']}")
        if n.get('detail'): lines.append(f"详情: {n['detail']}")
        lines.append("")
    return "\n".join(lines)

def get_local_global_news(curr_date: Annotated[str,"当前日期"], look_back_days: Annotated[int,"回顾天数"]=7, limit: Annotated[int,"最大条数"]=10) -> str:
    return f"# 宏观新闻\n# 来源: 本地新闻库\n# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n暂无宏观新闻数据 (可配置 ~/gupiao/news/ 分类目录)"
