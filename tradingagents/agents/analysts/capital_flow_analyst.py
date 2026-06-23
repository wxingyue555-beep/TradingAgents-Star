"""Capital Flow & Smart Money Tracking Analyst for A-share market."""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_capital_flow,
    get_indicators,
    get_language_instruction,
    get_stock_data,
)


def create_capital_flow_analyst(llm):
    """Capital flow and smart money tracking analyst.

    Analyzes: institutional positions (北向资金/机构持仓), margin trading,
    dragon-tiger list activity, major block/retail flow divergence,
    and insider transactions to gauge smart money positioning.
    """

    def capital_flow_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_stock_data, get_indicators, get_capital_flow]

        system_message = (
            "You are a capital flow and smart money analyst. Your role is to track where"
            " institutional and major capital is flowing, analyze position changes of key"
            " market participants (北向资金, 机构, 游资, 散户), and identify divergences"
            " between price action and capital flow that signal turning points."

            "\n\n**Capital Flow Analysis Framework:**"

            "\n\nStep 1 — Multi-dimensional capital flow assessment:"
            "\n  - Major net inflow (主力净流入): sustained inflow or outflow trend?"
            "\n  - Northbound capital (北向资金): consistent buying or selling? 持股比例变化?"
            "\n  - Margin trading (融资融券): 融资余额 trend — leverage sentiment indicator"
            "\n  - Block trades (大宗交易): premium or discount? Who is transferring to whom?"
            "\n  - Insider transactions (高管增减持): are executives buying or selling?"

            "\n\nStep 2 — Volume-price divergence detection:"
            "\n  - Price rising + volume declining = weakening momentum"
            "\n  - Price rising + major outflow = distribution (出货)"
            "\n  - Price falling + major inflow = accumulation (吸筹)"
            "\n  - Price flat + volume expansion = positioning ahead of catalyst"
            "\n  - Volume stall at highs = potential top formation"

            "\n\nStep 3 — Smart money vs. retail divergence:"
            "\n  - Are major/block orders buying while retail sells? (institutional accumulation)"
            "\n  - Are major/block orders selling while retail buys? (distribution warning)"
            "\n  - Large order ratio trend: increasing or decreasing?"

            "\n\nStep 4 — Capital flow signal synthesis:"
            "\n  - Overall capital flow rating: Strong Inflow / Moderate Inflow / Neutral / Moderate Outflow / Strong Outflow"
            "\n  - Alignment check: do capital flow signals align with technical signals?"
            "\n  - Leading indicator: is capital flow leading or lagging price action?"

            "\n\nUse get_stock_data for price/volume data, get_indicators for technical context,"
            " and get_capital_flow for institutional/block/retail flow data."
            " Focus on ACTIONABLE insights — does capital flow support or contradict the trade thesis?"
            + " Make sure to append a Markdown table at the end of the report to organize:"
            " capital flow rating, major order trends, volume-price signal,"
            " and smart money positioning."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = str(result.content) if result.content else "Capital flow analysis complete."

        return {
            "messages": [result],
            "capital_flow_report": report,
        }

    return capital_flow_node
