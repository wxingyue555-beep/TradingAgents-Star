from __future__ import annotations
import functools
import logging
from collections.abc import Mapping
from typing import Optional, Any

from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.fundamental_data_tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
)
from tradingagents.agents.utils.macro_data_tools import get_macro_indicators
from tradingagents.agents.utils.market_data_validation_tools import get_verified_market_snapshot
from tradingagents.agents.utils.news_data_tools import (
    get_capital_flow,
    get_global_news,
    get_insider_transactions,
    get_news,
)
from tradingagents.agents.utils.prediction_markets_tools import get_prediction_markets
from tradingagents.agents.utils.technical_indicators_tools import get_indicators

# Public surface: the data tools are imported here so agents and the graph
# import them from one place, plus the instrument/language helpers defined below.
__all__ = [
    "get_stock_data",
    "get_indicators",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_news",
    "get_global_news",
    "get_insider_transactions",
    "get_macro_indicators",
    "get_prediction_markets",
    "get_capital_flow",
    "get_verified_market_snapshot",
    "build_instrument_context",
    "resolve_instrument_identity",
    "get_instrument_context_from_state",
    "get_language_instruction",
    "get_reporting_rules",
    "clean_report_text",
    "create_msg_delete",
]

logger = logging.getLogger(__name__)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def get_reporting_rules() -> str:
    """Return anti-hallucination and unit-consistency rules shared across analysts."""
    return (
        "\n\n**REPORTING RULES:**"
        "\n- Volume unit: always use '万手' (10k lots), never '万股'. 1手=100股, A-share standard is 万手."
        "\n- Price unit: always in 元 (CNY) unless otherwise specified."
        "\n- Capital flow unit: 万元 (10k CNY), as labeled in the capital flow data header."
        "\n- NEVER fabricate figures not returned by tools. If a tool returns no data, say '数据不可用'."
        "\n- Do NOT compare data across periods (H1 vs Q3 vs FY) unless tools return multi-period data."
        "\n- If tool output has a header specifying units, respect it. Do not convert or reinterpret."
        "\n- Do NOT use marketing or sensational language (e.g. '终极火箭筒', '打骨折价', '爆赚'). Stay professional."
        "\n- Every numerical claim must cite its source tool or data line. Do not paraphrase data — quote exact values."
        "\n- If the same data point (close price, volume) appears in multiple tools, use the latest tool output as truth."
        "\n- CRITICAL: Today's OHLCV from get_verified_market_snapshot is the SINGLE source of truth for close price and volume."
        "\n  Do NOT use volume numbers from capital_flow (tick_trade table) as the daily volume — they are tick-level aggregates"
        "\n  with different counting conventions. Always cross-check volume against the verified snapshot."
        "\n- The company name resolved at run start is authoritative. Do NOT substitute a different company name."
        "\n  If you see a different name in tool output, flag the discrepancy rather than adopting the wrong name."
        "\n\n**RIGOR RULES — OP EXPERT MODE:**"
        "\n- Accuracy beats approval. Be blunt, argumentative. No disclaimers, no praise."
        "\n- Lead with counterarguments before stating your position."
        "\n- Do not capitulate without new evidence. Defend your position if the data supports it."
        "\n\n**EVIDENCE TAGGING — Tag EVERY factual claim:**"
        "\n  [KNOWN] = from training data · [COMPUTED] = calculated from tool data"
        "\n  [INFERRED] = logical deduction · [COMMON] = standard field knowledge"
        "\n  [FRAME] = from a symbolic/typological system, coherent in-frame but NOT real-world verified"
        "\n  [GUESS] = no basis — cap at LOW confidence, explicitly flag as speculation"
        "\n\n**FRAME→REALITY FORBIDDEN:** If you use a symbolic frame (technical pattern names,"
        "\n cycle theories, numerological levels), do NOT present the frame's conclusion as a"
        "\n real-world fact without flagging the translation. Keep the conclusion in-source."
        "\n\n**CONFIDENCE — append to EACH claim:** HIGH(≥80%) · MED(50-80%) · LOW(20-50%)"
        "\n · VERY LOW(<20%) · UNKNOWN. [FRAME] claims cap at LOW. [GUESS] claims cap at VERY LOW."
        "\n\n**DON'T KNOW:** If you genuinely lack sufficient data to answer, start with"
        "\n 'I don't know.' Do not bury uncertainty, do not fabricate to fill gaps."
        "\n\n**ANTI-SYCOPHANCY CHECK — Watch for these red flags:**"
        "\n- Unusually elegant explanation that ties everything together perfectly"
        "\n- One pattern explains all data points"
        "\n- Agreed with pushback without new evidence"
        "\n- Inserted specific-sounding details for unearned authority"
        "\n→ If detected: cut specifics, add [GUESS], or say 'I don't know.'"
        "\n\n**POST-HOC CHECK:** Would this analysis predict the outcome WITHOUT knowing it?"
        "\n If NO → tag as [INFERRED, post-hoc], note it accommodates but doesn't predict."
        "\n\n**NO FABRICATED CITATIONS.** Never invent paper titles, author names, or sources."
        "\n\n**SELF-REVISION:** If you realize you held a position just for consistency,"
        "\n revise openly. Append '[RULES I BROKE]: which, where, why.' at end of report."
    )


def clean_report_text(text: str) -> str:
    """Remove LLM conversational filler from report text.
    
    Strips common opening gambits like '好的，所有数据已经收集完毕...'
    and tool-call status reports that shouldn't appear in the final report.
    """
    import re
    if not text:
        return text
    patterns = [
        r'^好的[，,].*?。\s*',              # 好的，所有数据已经收集完毕。
        r'^现在[我我们已已经让让].*?。\s*',   # 现在我已获取.../现在让我撰写...
        r'^所有数据.*?准备.*?。\s*',          # 所有数据已准备好。
        r'^verified_.*?暂时不可用[。]?\s*',   # verified_xxx temporarily unavailable
        r'^让我.*?(?:撰写|分析|整理).*?。\s*', # 让我基于全部信息撰写详细报告。
        r'^Based on the .*?[,\.].*?\.\s*',    # Based on the data, I will...
        r'^Now (?:that )?I have .*?[,\.].*?\.\s*',  # Now that I have the data...
        r'^Let me .*?(?:write|analyze|compose).*?\.\s*',
        r'^I will now .*?\.\s*',
    ]
    for pat in patterns:
        text = re.sub(pat, '', text, count=1, flags=re.IGNORECASE)
    return text.strip()


def _resolve_name_from_watchlist(ticker: str) -> Optional[str]:
    """Look up a ticker's display name from the local watchlist directory.

    Falls back gracefully when the watchlist directory doesn't exist or
    the ticker isn't found, so the call site never needs a try/except.
    """
    try:
        from tradingagents.dataflows.local_db.watchlist import scan_watchlist
        wl = scan_watchlist()
        for code, info in wl.items():
            if info.get("symbol", "") == ticker:
                return info.get("name")
    except Exception:
        pass
    return None


@functools.lru_cache(maxsize=256)
def resolve_instrument_identity(ticker: str) -> dict:
    """Resolve company name for a ticker from the local watchlist.

    For A-share (.SH/.SZ/.BJ) and HK (.HK) stocks, uses the local watchlist
    directory. Returns identity dict with ``company_name`` if found, or ``{}``.
    """
    identity: dict[str, str] = {}

    company_name = _resolve_name_from_watchlist(ticker)
    if company_name:
        identity["company_name"] = company_name

    return identity


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    identity: Mapping[str, str] | None = None,
) -> str:
    """Describe the exact instrument so agents preserve identity and ticker.

    When ``identity`` is provided (resolved deterministically via
    :func:`resolve_instrument_identity`), the company name and business
    classification are injected so agents anchor to the real company rather
    than pattern-matching the price chart to a wrong one (#814).
    """
    is_crypto = asset_type == "crypto"
    instrument_label = "asset" if is_crypto else "instrument"
    context = (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
    )

    details = []
    if identity:
        name = identity.get("company_name") or identity.get("name")
        if name:
            details.append(f"{'Name' if is_crypto else 'Company'}: {name}")
        sector, industry = identity.get("sector"), identity.get("industry")
        if sector and industry:
            details.append(f"Business classification: {sector} / {industry}")
        elif sector:
            details.append(f"Sector: {sector}")
        elif industry:
            details.append(f"Industry: {industry}")
        if identity.get("exchange"):
            details.append(f"Exchange: {identity['exchange']}")

    if details:
        context += (
            f" Resolved identity: {'; '.join(details)}. "
            "Do not substitute a different company or ticker unless a tool "
            "result explicitly disproves this resolved identity."
        )

    if is_crypto:
        context += (
            " Treat it as a crypto asset rather than a company, and do not "
            "assume company fundamentals are available."
        )
    return context


def get_instrument_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the instrument context for the current run.

    Prefers the identity-resolved context computed once at run start and
    stored on the state (see ``TradingAgentsGraph.resolve_instrument_context``).
    Falls back to a ticker-only context — with no network lookup — when the
    state was constructed without it (bare programmatic states, tests), so a
    consumer is never forced to make a yfinance call mid-graph.
    """
    context = state.get("instrument_context")
    if isinstance(context, str) and context.strip():
        return context
    return build_instrument_context(
        str(state["company_of_interest"]),
        state.get("asset_type", "stock"),
    )


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add a context-anchored placeholder.

        The placeholder must not be a bare ``"Continue"``: some
        OpenAI-compatible providers interpret that literally as the user task
        and produce output about the word "continue" instead of analysing the
        instrument (#888). Anchoring it to the resolved instrument context and
        date keeps the next analyst on-task even if the provider treats the
        placeholder as a standalone request.
        """
        messages = state["messages"]
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        instrument_context = get_instrument_context_from_state(state)
        trade_date = state.get("trade_date", "the requested date")
        placeholder = HumanMessage(
            content=(
                f"Proceed with your assigned analysis for this workflow. "
                f"{instrument_context} The analysis date is {trade_date}."
            )
        )
        return {"messages": removal_operations + [placeholder]}

    return delete_messages



