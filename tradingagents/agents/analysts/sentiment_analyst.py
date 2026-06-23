"""Sentiment analyst — A-share multi-source sentiment analysis for a target ticker.

Refactored from the original StockTwits/Reddit-based version. For A-share stocks,
foreign social platforms rarely carry meaningful retail sentiment. Instead we use:

  1. Individual stock news — 新浪财经 + 财联社 + 东方财富公告 (via china_news vendor)
  2. Macro market pulse — 财联社电报 (via china_news global_news)
  3. Retail discussion gauged from news headline volume and repetition of key themes

The agent does not use tool-calling; the data is in the prompt from turn 0.
Output uses structured-output (SentimentReport schema) with free-text fallback.
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.utils.agent_utils import (
    get_global_news,
    get_instrument_context_from_state,
    get_language_instruction,
    get_news,
    get_reporting_rules,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches stock news + macro pulse from Chinese sources, injects them
    into the prompt as structured blocks, and produces a deterministic sentiment
    report via structured output.
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # A-share stock news: 新浪财经 + 财联社搜索 + 东方财富公告
        stock_news_block = get_news.func(ticker, start_date, end_date)
        # Macro market pulse: 财联社电报 (rapid-fire market headlines)
        macro_block = get_global_news.func(end_date, look_back_days=3, limit=12)

        system_message = _build_system_message(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            stock_news_block=stock_news_block,
            macro_block=macro_block,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}"
                    "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        formatted_messages = prompt.format_messages(messages=state["messages"])

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    stock_news_block: str,
    macro_block: str,
) -> str:
    """Assemble the sentiment-analyst system message with A-share data blocks."""
    return f"""You are an A-share market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on Chinese market data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### 个股新闻 — 新浪财经 + 财联社 + 东方财富公告，近 7 天
机构视角，事实驱动，较慢变化的信号。公告类（分红/业绩/减持）权重最高，其次为财联社快讯，再次为新浪综合新闻。

<start_of_stock_news>
{stock_news_block}
<end_of_stock_news>

### 宏观市场脉搏 — 财联社电报，近 3 天
高频快讯，反映市场整体情绪和板块轮动。用于评估大盘背景和行业情绪环境。

<start_of_macro_pulse>
{macro_block}
<end_of_macro_pulse>

## A 股情绪分析方法（最佳实践）

1. **区分公告事件与新闻评论。** 公告（"股东减持""业绩预告""分红方案"）是事实事件，权重最高；新闻标题中的情感词（"利好""承压""暴雷""涨停"）反映媒体框架，需去噪。

2. **寻找跨源分歧。** 如果公告偏正面但新闻标题偏负面，这种分歧本身就是信号——说明市场对同一事件的解读存在分歧。

3. **宏观背景定调。** 财联社电报的密集程度和关键词频率反映当日市场情绪温度。如果宏观快讯中频繁出现"下跌""调整""缩量"，个股负面新闻的权重应上调。

4. **区分观点与事件。** 新闻标题"XX公司宣布分红方案"是事件；"XX公司分红超预期，股价有望反弹"是观点。两者都是输入信号但权重不同。

5. **识别反复出现的叙事主题。** 哪些话题跨源反复出现？那是主导叙事。

6. **诚实对待数据限制。** 如果某只股票的新闻源返回"暂无相关新闻数据"，或某只冷门股仅有 2-3 条公告，情绪读数就不可靠——显式标记在 `confidence` 和 `narrative` 中。

7. **识别催化剂和风险。** 从公告中提取即将发生的催化剂（分红日/业绩预告窗口/解禁日）和风险（减持计划/诉讼公告）。

8. **过去的情绪不具预测性。** 将结论框定为交易员参考信号，而非价格预测。

## 输出字段

- **overall_band**: Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish 之一。出现明显跨源分歧时使用 Mixed；只有所有源都沉默时才用 Neutral。
- **overall_score**: 0（极度看空）到 10（极度看多）；5 为中性。与 overall_band 保持一致。
- **confidence**: low / medium / high，基于数据质量和样本量。
- **narrative**: 分源拆解、跨源分歧、主导叙事主题、催化剂和风险、以及关键情绪信号的 markdown 汇总表（方向、来源、支撑证据）。

{get_language_instruction()}
{get_reporting_rules()}"""


# ---------------------------------------------------------------------------
# Backwards-compatibility shim
# ---------------------------------------------------------------------------
def create_social_media_analyst(llm):
    """Deprecated alias for :func:`create_sentiment_analyst`.

    Kept so existing code that imports ``create_social_media_analyst``
    continues to work.

    .. deprecated::
        Import :func:`create_sentiment_analyst` directly instead.
    """
    import warnings
    warnings.warn(
        "create_social_media_analyst is deprecated; use create_sentiment_analyst",
        DeprecationWarning,
        stacklevel=2,
    )
    return create_sentiment_analyst(llm)
