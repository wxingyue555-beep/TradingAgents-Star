"""TradingAgents Web Interface — FastAPI + SSE + HTML Reports."""
import asyncio
import json
import logging
import os
import queue
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.dataflows.config import set_config
from tradingagents.agents.utils.agent_utils import clean_report_text
from .report_builder import build_html_report

logger = logging.getLogger(__name__)

app = FastAPI(title="TradingAgents Web", version="2.0")

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
if os.name == "nt":
    RESULTS_DIR = Path(r"D:\BaiduSyncdisk\data\outroport")
else:
    RESULTS_DIR = Path.home() / "gupiao" / "data" / "outroport"

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_active_runs: dict[str, dict] = {}

NODE_LABELS = {
    "Market Analyst": "市场分析",
    "tools_market": "市场分析 · 数据查询",
    "Msg Clear Market": "市场分析 · 完成",
    "Sentiment Analyst": "情绪分析",
    "tools_social": "情绪分析 · 数据查询",
    "Msg Clear Sentiment": "情绪分析 · 完成",
    "News Analyst": "新闻分析",
    "tools_news": "新闻分析 · 数据查询",
    "Msg Clear News": "新闻分析 · 完成",
    "Fundamentals Analyst": "基本面分析",
    "tools_fundamentals": "基本面 · 数据查询",
    "Msg Clear Fundamentals": "基本面 · 完成",
    "Industry_chain Analyst": "产业链分析",
    "tools_industry_chain": "产业链 · 数据查询",
    "Msg Clear Industry_chain": "产业链 · 完成",
    "Capital_flow Analyst": "资金流向分析",
    "tools_capital_flow": "资金流向 · 数据查询",
    "Msg Clear Capital_flow": "资金流向 · 完成",
    "Bull Researcher": "研究员辩论 · 看涨",
    "Bear Researcher": "研究员辩论 · 看跌",
    "Research Manager": "研究经理 · 裁决",
    "Trader": "交易员 · 方案制定",
    "Aggressive Analyst": "风控 · 激进评估",
    "Conservative Analyst": "风控 · 保守评估",
    "Neutral Analyst": "风控 · 中性评估",
    "Portfolio Manager": "组合经理 · 最终决策",
}


class AnalyzeRequest(BaseModel):
    ticker: str = "600000.SH"
    trade_date: str = "2026-06-20"
    analysts: str = "market,social,news,fundamentals,industry_chain,capital_flow"
    provider: str = "deepseek"
    deep_model: str = "deepseek-v4-pro"
    quick_model: str = "deepseek-v4-flash"
    debate_rounds: int = 1
    risk_rounds: int = 1
    news_dir: str = ""


def _build_config(provider, deep_model, quick_model, debate_rounds, risk_rounds):
    cfg = DEFAULT_CONFIG.copy()
    if provider:
        cfg["llm_provider"] = provider
    if deep_model:
        cfg["deep_think_llm"] = deep_model
    if quick_model:
        cfg["quick_think_llm"] = quick_model
    cfg["output_language"] = "Chinese"
    cfg["max_debate_rounds"] = debate_rounds
    cfg["max_risk_discuss_rounds"] = risk_rounds
    cfg["results_dir"] = str(RESULTS_DIR)
    cfg["data_vendors"]["core_stock_apis"] = "local_db"
    cfg["data_vendors"]["technical_indicators"] = "local_db"
    cfg["data_vendors"]["fundamental_data"] = "local_db"
    cfg["data_vendors"]["news_data"] = "china_news"
    return cfg


def _build_markdown_report(final_state: dict, ticker: str, trade_date: str, stock_name: str) -> str:
    """Build a consolidated Markdown report from the analysis final state."""
    title = f"{stock_name} ({ticker})" if stock_name else ticker
    lines = [
        f"# {title} 交易分析报告",
        f"**交易日期**: {trade_date}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    # 分析师报告
    sections = [
        ("市场分析", "market_report"),
        ("情绪分析", "sentiment_report"),
        ("新闻分析", "news_report"),
        ("基本面分析", "fundamentals_report"),
        ("产业链分析", "industry_chain_report"),
        ("资金流向分析", "capital_flow_report"),
    ]
    has_analyst = False
    for label, key in sections:
        text = clean_report_text(final_state.get(key, ""))
        if text:
            has_analyst = True
            lines.append(f"## {label}")
            lines.append("")
            lines.append(text)
            lines.append("")
    if not has_analyst:
        lines.append("## 分析师报告")
        lines.append("")
        lines.append("_暂无分析师报告_")
        lines.append("")

    # 研究团队辩论
    debate = final_state.get("investment_debate_state", {})
    if debate:
        lines.append("---")
        lines.append("")
        lines.append("## 研究团队辩论")
        lines.append("")
        if debate.get("bull_history"):
            lines.append("### 看涨研究员")
            lines.append("")
            lines.append(debate["bull_history"])
            lines.append("")
        if debate.get("bear_history"):
            lines.append("### 看跌研究员")
            lines.append("")
            lines.append(debate["bear_history"])
            lines.append("")

    # 研究经理裁决
    invest_plan = final_state.get("investment_plan", "")
    if invest_plan:
        lines.append("---")
        lines.append("")
        lines.append("## 研究经理裁决")
        lines.append("")
        lines.append(invest_plan)
        lines.append("")

    # 交易员方案
    trader_plan = final_state.get("trader_investment_plan", "")
    if trader_plan:
        lines.append("---")
        lines.append("")
        lines.append("## 交易员方案")
        lines.append("")
        lines.append(trader_plan)
        lines.append("")

    # 风控辩论
    risk = final_state.get("risk_debate_state", {})
    if risk:
        lines.append("---")
        lines.append("")
        lines.append("## 风控团队辩论")
        lines.append("")
        if risk.get("aggressive_history"):
            lines.append("### 激进评估")
            lines.append("")
            lines.append(risk["aggressive_history"])
            lines.append("")
        if risk.get("conservative_history"):
            lines.append("### 保守评估")
            lines.append("")
            lines.append(risk["conservative_history"])
            lines.append("")
        if risk.get("neutral_history"):
            lines.append("### 中性评估")
            lines.append("")
            lines.append(risk["neutral_history"])
            lines.append("")

    # 最终决策
    final_decision = final_state.get("final_trade_decision", "")
    if final_decision:
        lines.append("---")
        lines.append("")
        lines.append("## 最终决策")
        lines.append("")
        lines.append(final_decision)
        lines.append("")

    return "\n".join(lines)


def _run_analysis(run_id, ticker, trade_date, analysts, provider, deep_model, quick_model, debate_rounds, risk_rounds, news_dir=""):
    q = _active_runs[run_id]["queue"]
    try:
        # Normalize ticker: auto-append market suffix for A-shares
        raw_ticker = ticker.strip()
        if not any(raw_ticker.endswith(s) for s in (".SH", ".SZ", ".BJ")):
            # Infer market from code prefix
            code_str = raw_ticker.zfill(6) if raw_ticker.isdigit() else raw_ticker
            if code_str.startswith(("60", "68")):
                ticker = raw_ticker + ".SH"
            elif code_str.startswith(("00", "30")):
                ticker = raw_ticker + ".SZ"
            elif code_str.startswith(("83", "87", "92")):
                ticker = raw_ticker + ".BJ"
        q.put({"event": "start", "data": {"ticker": ticker, "date": trade_date}})
        cfg = _build_config(provider, deep_model, quick_model, debate_rounds, risk_rounds)
        if news_dir:
            cfg["news_dir"] = news_dir
            import os; os.environ["TRADINGAGENTS_LOCAL_NEWS_DIR"] = news_dir
        set_config(cfg)
        q.put({"event": "progress", "data": {"node": "__init__", "label": "初始化中...", "step": 0}})

        graph = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=cfg)
        q.put({"event": "progress", "data": {"node": "__init__", "label": "图引擎就绪", "step": 0}})

        instrument_ctx = graph.resolve_instrument_context(ticker)
        init_state = graph.propagator.create_initial_state(
            ticker, trade_date,
            asset_type="stock",
            instrument_context=instrument_ctx,
        )

        base_cfg = {"recursion_limit": graph.propagator.max_recur_limit}
        final_state = None
        step = 0

        for item in graph.graph.stream(init_state, stream_mode=["updates", "values"], config=base_cfg):
            mode, payload = item
            if mode == "updates":
                for node_id in payload:
                    step += 1
                    label = NODE_LABELS.get(node_id, node_id)
                    q.put({"event": "progress", "data": {"node": node_id, "label": label, "step": step}})
            elif mode == "values":
                final_state = payload

        if final_state is None:
            raise RuntimeError("Graph produced no final state")

        safe_ticker = ticker.replace("/", "_").replace("\\", "_")
        report_dir = Path(cfg["results_dir"]) / safe_ticker
        report_dir.mkdir(parents=True, exist_ok=True)
        # Look up stock name
        code_num = ticker.replace(".SH","").replace(".SZ","").replace(".BJ","")
        stock_name = _A_SHARE_NAMES.get(code_num, "")
        # Fallback: check watchlist
        if not stock_name:
            try:
                from tradingagents.dataflows.local_db import scan_watchlist
                wl = scan_watchlist()
                for wl_code, info in wl.items():
                    if info.get("symbol", "") == ticker:
                        stock_name = info.get("name", "")
                        break
            except Exception:
                pass
        # Build filename: 中文名_代码_日期_时分.html
        label = stock_name or ticker
        now_str = datetime.now().strftime("%H%M")
        html_path = report_dir / f"{label}_{code_num}_{trade_date}_{now_str}.html"
        html_content = build_html_report(final_state, ticker, trade_date, stock_name)
        html_path.write_text(html_content, encoding="utf-8")

        # Generate Markdown report alongside HTML
        md_path = report_dir / f"{label}_{code_num}_{trade_date}_{now_str}.md"
        md_content = _build_markdown_report(final_state, ticker, trade_date, stock_name)
        md_path.write_text(md_content, encoding="utf-8")

        decision = graph.process_signal(final_state.get("final_trade_decision", ""))
        _active_runs[run_id]["html_path"] = str(html_path)
        q.put({"event": "complete", "data": {"decision": decision, "html_path": str(html_path), "run_id": run_id}})
    except Exception as e:
        logger.exception("Analysis failed for %s", ticker)
        q.put({"event": "error", "data": {"message": str(e)}})
    finally:
        q.put({"event": "done", "data": {}})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    run_id = uuid.uuid4().hex[:12]
    analyst_list = [a.strip() for a in req.analysts.split(",") if a.strip()]
    q = queue.Queue()
    _active_runs[run_id] = {"queue": q, "started": datetime.now()}
    thread = threading.Thread(
        target=_run_analysis,
        args=(run_id, req.ticker, req.trade_date, analyst_list, req.provider, req.deep_model, req.quick_model, req.debate_rounds, req.risk_rounds, req.news_dir),
        daemon=True,
    )
    thread.start()

    async def event_stream():
        while True:
            try:
                msg = q.get(timeout=120)
                yield f"data: {json.dumps(msg, default=str)}\n\n"
                if msg["event"] in ("complete", "error", "done"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'event': 'timeout', 'data': {}})}\n\n"
                break
        await asyncio.sleep(10)
        _active_runs.pop(run_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")





# Built-in A-share stock name mapping (stock_basic.name is NULL in local DB)
_A_SHARE_NAMES = {
    "600000": "浦发银行", "600004": "白云机场", "600009": "上海机场", "600010": "包钢股份",
    "600015": "华夏银行", "600016": "民生银行", "600018": "上港集团", "600019": "宝钢股份",
    "600025": "华能水电", "600028": "中国石化", "600029": "南方航空", "600030": "中信证券",
    "600031": "三一重工", "600036": "招商银行", "600048": "保利发展", "600050": "中国联通",
    "600056": "中国医药", "600085": "同仁堂", "600104": "上汽集团", "600111": "北方稀土",
    "600115": "中国东航", "600150": "中国船舶", "600196": "复星医药", "600276": "恒瑞医药",
    "600309": "万华化学", "600340": "华夏幸福", "600346": "恒力石化", "600406": "国电南瑞",
    "600436": "片仔癀", "600438": "通威股份", "600519": "贵州茅台", "600547": "山东黄金",
    "600570": "恒生电子", "600585": "海螺水泥", "600588": "用友网络", "600690": "海尔智家",
    "600703": "三安光电", "600745": "闻泰科技", "600809": "山西汾酒", "600837": "海通证券",
    "600887": "伊利股份", "600893": "航发动力", "600900": "长江电力", "600905": "三峡能源",
    "600941": "中国移动", "601006": "大秦铁路", "601012": "隆基绿能", "601088": "中国神华",
    "601111": "中国国航", "601138": "工业富联", "601166": "兴业银行", "601211": "国泰君安",
    "601288": "农业银行", "601318": "中国平安", "601328": "交通银行", "601390": "中国中铁",
    "601398": "工商银行", "601601": "中国太保", "601628": "中国人寿", "601633": "长城汽车",
    "601668": "中国建筑", "601688": "华泰证券", "601728": "中国电信", "601766": "中国中车",
    "601800": "中国交建", "601816": "京沪高铁", "601857": "中国石油", "601888": "中国中免",
    "601899": "紫金矿业", "601919": "中远海控", "601939": "建设银行", "601985": "中国核电",
    "601988": "中国银行", "601995": "中金公司", "603019": "中科曙光", "603259": "药明康德",
    "603288": "海天味业", "603501": "韦尔股份", "603986": "兆易创新",
    "688001": "华兴源创", "688005": "容百科技", "688008": "澜起科技", "688009": "中国通号",
    "688012": "中微公司", "688036": "传音控股", "688041": "海光信息", "688047": "龙芯中科",
    "688111": "金山办公", "688126": "沪硅产业", "688187": "时代电气", "688223": "晶科能源",
    "688256": "寒武纪", "688271": "联影医疗", "688303": "大全能源", "688396": "华润微",
    "688561": "奇安信", "688981": "中芯国际",
    "000001": "平安银行", "000002": "万科A", "000063": "中兴通讯", "000100": "TCL科技",
    "000157": "中联重科", "000301": "东方盛虹", "000333": "美的集团", "000338": "潍柴动力",
    "000425": "徐工机械", "000538": "云南白药", "000568": "泸州老窖", "000596": "古井贡酒",
    "000625": "长安汽车", "000651": "格力电器", "000661": "长春高新", "000725": "京东方A",
    "000776": "广发证券", "000792": "盐湖股份", "000800": "一汽解放", "000858": "五粮液",
    "000876": "新希望", "000977": "浪潮信息", "002049": "紫光国微", "002142": "宁波银行",
    "002230": "科大讯飞", "002241": "歌尔股份", "002271": "东方雨虹", "002304": "洋河股份",
    "002311": "海大集团", "002352": "顺丰控股", "002371": "北方华创", "002415": "海康威视",
    "002459": "晶澳科技", "002460": "赣锋锂业", "002466": "天齐锂业", "002475": "立讯精密",
    "002493": "荣盛石化", "002594": "比亚迪", "002601": "龙佰集团", "002603": "以岭药业",
    "002714": "牧原股份", "002920": "德赛西威", "003816": "中国广核",
    "300015": "爱尔眼科", "300033": "同花顺", "300059": "东方财富", "300122": "智飞生物",
    "300124": "汇川技术", "300274": "阳光电源", "300413": "芒果超媒", "300450": "先导智能",
    "300498": "温氏股份", "300750": "宁德时代", "300760": "迈瑞医疗",
}

def _search_by_name(q: str, watchlist: dict, limit: int = 10) -> list:
    """Search stocks by Chinese name in built-in map + watchlist."""
    results = []
    q_lower = q.lower().strip()
    # Search built-in names
    for code, name in _A_SHARE_NAMES.items():
        if q_lower in name.lower() or q_lower in code:
            sym = code + (".SH" if code.startswith(("60","68")) else ".SZ" if code.startswith(("00","30")) else ".BJ")
            results.append({"code": code, "symbol": sym, "name": name})
    # Search watchlist names
    for wl_code, info in watchlist.items():
        sym = info.get("symbol", "")
        wl_name = info.get("name", "")
        code_num = sym.replace(".SH","").replace(".SZ","").replace(".BJ","")
        if q_lower in wl_name.lower() and code_num not in {r["code"] for r in results}:
            results.append({"code": code_num, "symbol": sym, "name": wl_name})
    return results[:limit]


@app.get("/api/search_stock")
async def search_stock(q: str = ""):
    """Search for A-share stocks by code or name."""
    from tradingagents.dataflows.local_db import search_local_stock, resolve_local_symbol, scan_watchlist
    q = q.strip()
    if not q:
        # Return watchlist stocks as suggestions
        wl = scan_watchlist()
        results = []
        for code, info in list(wl.items())[:20]:
            sym = info["symbol"]
            # Strip suffix for display
            code_num = sym.replace(".SH","").replace(".SZ","").replace(".BJ","")
            results.append({"code": code_num, "symbol": sym, "name": info["name"]})
        return results[:10]
    
    # Try resolve_local_symbol for exact code matches
    resolved = resolve_local_symbol(q)
    if resolved["ok"]:
        sym = resolved["symbol"]
        code_num = sym.replace(".SH","").replace(".SZ","").replace(".BJ","")
        return [{"code": code_num, "symbol": sym, "name": resolved["name"] or ""}]
    
    # Fallback: try local_db search for code matches
    search_result = search_local_stock(q)
    results = []
    for line in search_result.split("\n"):
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].endswith((".SH",".SZ",".BJ")):
            sym = parts[0]
            code_num = sym.replace(".SH","").replace(".SZ","").replace(".BJ","")
            name = _A_SHARE_NAMES.get(code_num, "")
            results.append({"code": code_num, "symbol": sym, "name": name})
    
    # If no code matches, try name search in built-in map + watchlist
    if not results:
        wl = scan_watchlist()
        results = _search_by_name(q, wl)
    
    return results[:10]

@app.get("/api/reports")
async def list_reports():
    """List all generated reports."""
    import re
    from tradingagents.dataflows.local_db import scan_watchlist
    results = []
    logs_dir = RESULTS_DIR
    if not logs_dir.exists():
        return results
    
    for ticker_dir in sorted(logs_dir.iterdir()):
        if not ticker_dir.is_dir():
            continue
        report_subdir = ticker_dir
        if not report_subdir.exists():
            continue
        
        # Find HTML reports (supports both: 名_码_日期_时分.html and report_日期.html)
        for html_file in sorted(report_subdir.glob("*.html"), reverse=True):
            fname = html_file.name
            # New format: 日月股份_603218_2026-06-23_1908.html
            m = re.match(r".*_(\d{4}-\d{2}-\d{2})_\d{4}\.html$", fname)
            if m:
                trade_date = m.group(1)
            else:
                # Old format: report_2026-06-23.html
                m2 = re.match(r"report_(.*)\.html", fname)
                trade_date = m2.group(1) if m2 else ""
            if not trade_date:
                continue
            
            # Try to extract decision from the HTML
            html_text = html_file.read_text(encoding="utf-8", errors="ignore")
            decision = ""
            for tag in ['badge-buy','badge-sell','badge-hold','badge-underweight','badge-overweight','badge-neutral']:
                if tag in html_text:
                    decision = tag.replace('badge-','')
                    break
            
            # Get file stats
            stat = html_file.stat()
            
            # Look up stock name
            code_num = ticker_dir.name.replace(".SH","").replace(".SZ","").replace(".BJ","")
            stock_name = _A_SHARE_NAMES.get(code_num, "")
            # Also check watchlist
            if not stock_name:
                wl = scan_watchlist()
                for wl_code, info in wl.items():
                    if info.get("symbol","") == ticker_dir.name:
                        stock_name = info.get("name","")
                        break
            
            results.append({
                "ticker": ticker_dir.name,
                "code": code_num,
                "name": stock_name,
                "trade_date": trade_date,
                "decision": decision,
                "size_kb": round(stat.st_size / 1024, 1),
                "generated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "view_url": f"/api/report/view/{ticker_dir.name}/{trade_date}",
            })
    
    return sorted(results, key=lambda r: r["generated_at"], reverse=True)


@app.get("/api/report/view/{ticker}/{trade_date}")
async def view_report(ticker: str, trade_date: str):
    """View a generated report by ticker and date."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    report_dir = RESULTS_DIR / safe_ticker
    if report_dir.exists():
        # Match both new format (名_码_日期_时分.html) and old format (report_日期.html)
        candidates = sorted(report_dir.glob(f"*{trade_date}*.html"), reverse=True)
        if candidates:
            return FileResponse(str(candidates[0]), media_type="text/html")
    return HTMLResponse("<h2>报告未找到</h2>", status_code=404)

@app.get("/api/report/{run_id}")
async def get_report(run_id: str):
    html_path = _active_runs.get(run_id, {}).get("html_path", "")
    if html_path and Path(html_path).exists():
        return FileResponse(html_path, media_type="text/html",
                           filename=f"TradingAgents_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    return HTMLResponse("<h2>报告不存在或已过期，请重新运行分析。</h2>", status_code=404)
