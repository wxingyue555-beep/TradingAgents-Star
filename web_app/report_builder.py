"""Convert TradingAgents final state into a complete standalone HTML report."""
from datetime import datetime


def _section(title: str, body: str, icon: str = "📊", collapsed: bool = False) -> str:
    """Render a collapsible report section."""
    display = "none" if collapsed else "block"
    return f'''
    <div class="section">
        <div class="section-header" onclick="toggleSection(this)">
            <span class="section-icon">{icon}</span>
            <h2>{title}</h2>
            <span class="toggle-arrow">{'▶' if collapsed else '▼'}</span>
        </div>
        <div class="section-body" style="display:{display}">
            {body}
        </div>
    </div>'''


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _md_to_html(md: str) -> str:
    """Simple markdown-to-HTML converter for analyst reports."""
    if not md:
        return "<p class='empty'>No report available.</p>"

    lines = md.split("\n")
    html_lines = []
    in_table = False
    in_code = False
    table_rows = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("#"):
            continue

        if stripped.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            html_lines.append(line)
            continue

        if "|" in stripped and stripped.count("|") >= 2 and not in_table:
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            if len(parts) >= 2:
                in_table = True
                table_rows = [parts]
                continue

        if in_table:
            if "|" in stripped and stripped.count("|") >= 2:
                parts = [p.strip() for p in stripped.split("|") if p.strip()]
                if not all(p.replace("-", "").replace(":", "") == "" for p in parts):
                    table_rows.append(parts)
                continue
            else:
                if table_rows:
                    html_lines.append('<table class="report-table">')
                    html_lines.append("<thead><tr>" + "".join(f"<th>{_escape_html(c)}</th>" for c in table_rows[0]) + "</tr></thead>")
                    html_lines.append("<tbody>")
                    for row in table_rows[1:]:
                        html_lines.append("<tr>" + "".join(f"<td>{_escape_html(c)}</td>" for c in row) + "</tr>")
                    html_lines.append("</tbody></table>")
                in_table = False
                table_rows = []

        if stripped.startswith("## "):
            html_lines.append(f"<h3>{_escape_html(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h4>{_escape_html(stripped[2:])}</h4>")
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{_escape_html(stripped[2:])}</li>")
        elif stripped.startswith("* "):
            html_lines.append(f"<li>{_escape_html(stripped[2:])}</li>")
        elif stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            html_lines.append(f"<li>{_escape_html(stripped)}</li>")
        elif stripped.startswith("**") and "**" in stripped[2:]:
            html_lines.append(f"<p><strong>{_escape_html(stripped.strip('*'))}</strong></p>")
        elif not stripped:
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{_escape_html(stripped)}</p>")

    if in_table and table_rows:
        html_lines.append('<table class="report-table">')
        html_lines.append("<thead><tr>" + "".join(f"<th>{_escape_html(c)}</th>" for c in table_rows[0]) + "</tr></thead>")
        html_lines.append("<tbody>")
        for row in table_rows[1:]:
            html_lines.append("<tr>" + "".join(f"<td>{_escape_html(c)}</td>" for c in row) + "</tr>")
        html_lines.append("</tbody></table>")

    return "\n".join(html_lines)


def build_html_report(final_state: dict, ticker: str, trade_date: str, stock_name: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    market = final_state.get("market_report", "")
    sentiment = final_state.get("sentiment_report", "")
    news = final_state.get("news_report", "")
    fundamentals = final_state.get("fundamentals_report", "")
    industry = final_state.get("industry_chain_report", "")
    capital = final_state.get("capital_flow_report", "")
    debate = final_state.get("investment_debate_state", {})
    trader_plan = final_state.get("trader_investment_plan", "")
    risk = final_state.get("risk_debate_state", {})
    final_decision = final_state.get("final_trade_decision", "")

    decision_text = final_decision
    dt = decision_text.lower()
    if "买入" in dt or "buy" in dt:
        rating_badge = '<span class="badge badge-buy">买入</span>'
    elif "增持" in dt or "overweight" in dt:
        rating_badge = '<span class="badge badge-overweight">增持</span>'
    elif "减持" in dt or "underweight" in dt or "减仓" in dt:
        rating_badge = '<span class="badge badge-underweight">减持</span>'
    elif "卖出" in dt or "sell" in dt:
        rating_badge = '<span class="badge badge-sell">卖出</span>'
    elif "持有" in dt or "hold" in dt or "观望" in dt or "中性" in dt or "neutral" in dt:
        rating_badge = '<span class="badge badge-hold">持有</span>'
    else:
        rating_badge = '<span class="badge badge-neutral">待定</span>'

    sections = []

    if market:
        sections.append(_section("市场分析", _md_to_html(market), "📈"))
    if sentiment:
        sections.append(_section("情绪分析", _md_to_html(sentiment), "💬"))
    if news:
        sections.append(_section("新闻分析", _md_to_html(news), "📰"))
    if fundamentals:
        sections.append(_section("基本面分析", _md_to_html(fundamentals), "📋"))
    if industry:
        sections.append(_section("产业链分析", _md_to_html(industry), "🔗"))
    if capital:
        sections.append(_section("资金流向分析", _md_to_html(capital), "💰"))

    debate_html = ""
    if debate.get("bull_history"):
        debate_html += _section("看涨研究员", _md_to_html(debate["bull_history"]), "🐂", True)
    if debate.get("bear_history"):
        debate_html += _section("看跌研究员", _md_to_html(debate["bear_history"]), "🐻", True)
    if debate.get("judge_decision"):
        debate_html += _section("研究经理裁决", _md_to_html(debate["judge_decision"]), "⚖️", True)
    if debate_html:
        sections.append(f'<div class="section-group"><h2 class="group-title">🔬 研究团队辩论</h2>{debate_html}</div>')

    if trader_plan:
        sections.append(_section("交易方案", _md_to_html(trader_plan), "📝"))

    risk_html = ""
    if risk.get("aggressive_history"):
        risk_html += _section("激进评估", _md_to_html(risk["aggressive_history"]), "🔥", True)
    if risk.get("conservative_history"):
        risk_html += _section("保守评估", _md_to_html(risk["conservative_history"]), "🛡️", True)
    if risk.get("neutral_history"):
        risk_html += _section("中性评估", _md_to_html(risk["neutral_history"]), "⚖️", True)
    if risk_html:
        sections.append(f'<div class="section-group"><h2 class="group-title">🛡️ 风控团队</h2>{risk_html}</div>')

    fd = final_decision or risk.get("judge_decision", "")
    if fd:
        sections.append(_section("最终交易决策", _md_to_html(fd), "🎯"))

    css = '''
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f6f8fa; color: #1f2328; line-height:1.7; }
    .container { max-width:1100px; margin:0 auto; padding:30px 20px; }
    .report-header { background: linear-gradient(135deg, #0969da 0%, #8250df 100%); border-radius:16px; padding:40px; margin-bottom:30px; border:1px solid #d0d7de; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
    .report-header h1 { font-size:2em; color:#fff; margin-bottom:8px; }
    .report-header .meta { color:rgba(255,255,255,0.8); font-size:0.95em; }
    .badge { display:inline-block; padding:6px 18px; border-radius:20px; font-weight:700; font-size:1.1em; margin-top:12px; }
    .badge-buy { background:#dafbe1; color:#1a7f37; }
    .badge-sell { background:#ffebe9; color:#cf222e; }
    .badge-underweight { background:#fff1e6; color:#bc4c00; }
    .badge-overweight { background:#ddf4ff; color:#0550ae; }
    .badge-hold { background:#fff8c5; color:#9a6700; }
    .badge-neutral { background:#f3f4f6; color:#656d76; }
    .section-group { margin-bottom:24px; }
    .group-title { font-size:1.3em; color:#0969da; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #d0d7de; }
    .section { background:#ffffff; border-radius:12px; margin-bottom:16px; border:1px solid #d0d7de; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
    .section-header { display:flex; align-items:center; gap:12px; padding:16px 24px; cursor:pointer; user-select:none; transition:background .2s; background:#f6f8fa; }
    .section-header:hover { background:#ebedf0; }
    .section-header h2 { font-size:1.1em; color:#1f2328; flex:1; }
    .section-icon { font-size:1.3em; }
    .toggle-arrow { color:#656d76; font-size:0.85em; transition:transform .2s; }
    .section-body { padding:0 24px 24px; }
    .section-body h3 { color:#0969da; font-size:1.05em; margin:16px 0 8px; }
    .section-body h4 { color:#1f2328; font-size:1em; margin:12px 0 6px; }
    .section-body p { margin:4px 0; color:#1f2328; font-size:0.95em; }
    .section-body li { margin:2px 0 2px 20px; color:#1f2328; font-size:0.95em; }
    .section-body pre { background:#f6f8fa; border-radius:8px; padding:16px; overflow-x:auto; border:1px solid #d0d7de; }
    .section-body code { font-family:monospace; font-size:0.85em; color:#1a7f37; }
    .report-table { width:100%; border-collapse:collapse; margin:12px 0; font-size:0.9em; }
    .report-table th { background:#f6f8fa; color:#0969da; padding:10px 14px; text-align:left; border-bottom:2px solid #d0d7de; font-weight:600; }
    .report-table td { padding:8px 14px; border-bottom:1px solid #d0d7de; color:#1f2328; }
    .report-table tr:hover td { background:#f3f4f6; }
    .empty { color:#656d76; font-style:italic; padding:12px 0; }
    .report-footer { text-align:center; color:#656d76; font-size:0.85em; padding:30px 0 10px; border-top:1px solid #d0d7de; margin-top:40px; }
    @media(max-width:768px) { .container{padding:15px;} .report-header{padding:24px;} .section-header{padding:12px 16px;} .section-body{padding:0 16px 16px;} }
    '''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TradingAgents — {_escape_html(ticker)}{(" " + _escape_html(stock_name)) if stock_name else ""} 分析报告</title>
<style>{css}</style>
<script>
    function toggleSection(el) {{
        const body = el.nextElementSibling;
        const arrow = el.querySelector('.toggle-arrow');
        if (body.style.display === 'none') {{
            body.style.display = 'block';
            arrow.textContent = '▼';
        }} else {{
            body.style.display = 'none';
            arrow.textContent = '▶';
        }}
    }}
</script>
</head>
<body>
<div class="container">
<div class="report-header">
<h1>{_escape_html(stock_name) if stock_name else ""} {_escape_html(ticker)} 交易分析报告</h1>
<div class="meta">
分析日期: {trade_date} | 生成时间: {now} | 框架: TradingAgents v3.0 · A股多智能体
</div>
{rating_badge}
</div>
{"".join(sections)}
<div class="report-footer">
TradingAgents · 多智能体金融分析框架<br>
本报告由 AI 智能体团队自动生成，仅供参考，不构成投资建议。
</div>
</div>
</body>
</html>'''

    return html
