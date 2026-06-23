"""Industry Chain & Sector Dynamics Analyst for A-share market."""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_stock_data,
    get_indicators,
)


def create_industry_chain_analyst(llm):
    """Industry chain and sector dynamics analyst.

    Analyzes: upstream/downstream relationships, sector positioning,
    peer comparison, supply chain dependencies, and sector rotation signals.
    """

    def industry_chain_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_stock_data, get_indicators]

        system_message = (
            "You are an industry chain and sector dynamics analyst. Your role is to understand"
            " where this company sits in its industry value chain, analyze upstream and downstream"
            " dependencies, compare against sector peers, and identify sector-level trends that"
            " affect this stock's outlook."

            "\n\n**Industry Chain Analysis Framework:**"

            "\n\nStep 1 — Map the company's position in the value chain:"
            "\n  - Identify: upstream suppliers (原材料/核心零部件), midstream position (制造/集成),"
            "\n    downstream customers (终端应用/消费者)"
            "\n  - Key dependencies: which nodes are bottlenecks? Which nodes have pricing power?"
            "\n  - Vertical integration: is the company expanding across the chain?"

            "\n\nStep 2 — Sector competitive landscape:"
            "\n  - Market share and position (龙头/中军/跟风/边缘)"
            "\n  - Competitive moat: technology, brand, scale, regulation, switching cost"
            "\n  - Key competitors and their relative positioning"
            "\n  - Industry concentration: fragmented vs. oligopolistic"

            "\n\nStep 3 — Sector cycle and rotation analysis:"
            "\n  - Where is the sector in its cycle: early recovery / expansion / peak / contraction?"
            "\n  - Sector rotation signal: is capital flowing into or out of this sector?"
            "\n  - Compare sector trend vs. broad market trend (relative strength)"
            "\n  - Identify leading indicators for sector inflection points"

            "\n\nStep 4 — Supply chain risk assessment:"
            "\n  - Raw material price exposure and pass-through ability"
            "\n  - Customer concentration risk (single large customer?)"
            "\n  - Geographic/supply chain disruption risk"
            "\n  - Currency/commodity sensitivity"

            "\n\nStep 5 — Policy and regulatory landscape:"
            "\n  - Current policy stance: supportive / neutral / restrictive"
            "\n  - Recent regulatory changes or upcoming policy milestones"
            "\n  - Subsidies, tax incentives, or trade restrictions affecting the industry"

            "\n\nStep 6 — Peer comparison and relative valuation:"
            "\n  - Compare key metrics against 3-5 closest peers"
            "\n  - Relative strength: is this stock leading or lagging the sector?"
            "\n  - Valuation premium/discount relative to sector average"

            "\n\nUse the available tools get_stock_data and get_indicators to pull price, volume,"
            " and technical data. Focus your report on INDUSTRY-LEVEL insights that inform"
            " the stock's outlook, not generic macro commentary."
            + " Make sure to append a Markdown table at the end of the report to organize:"
            " value chain position, competitive ranking, sector cycle phase,"
            " and key peer comparison metrics."
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
            report = str(result.content) if result.content else "Industry chain analysis complete."

        return {
            "messages": [result],
            "industry_chain_report": report,
        }

    return industry_chain_node
