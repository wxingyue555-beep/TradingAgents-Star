"""Data vendor routing — A-share / 港股通 local-only mode.

All foreign vendors (yfinance, Alpha Vantage, FRED, Polymarket) have been removed.
Active vendors: local_db (通达信), local_news_api (starweb.cpolar.io → news.db),
and china_news (备用: 新浪/财联社/东方财富).

Default news_data vendor is now local_news_api — reads from pre-classified
local database instead of scraping live sources, reducing noise.
"""
import logging

from .config import get_config
from .errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
# ===== Local Chinese data sources =====
from .china_news import get_china_stock_news, get_china_global_news
from .local_news_api import get_local_news_api, get_local_global_news_api
from .local_db import (
    get_local_stock_data,
    get_local_fundamentals,
    get_local_balance_sheet,
    get_local_cashflow,
    get_local_income_statement,
    get_local_indicators,
    get_local_capital_flow,
    get_local_news,
    get_local_global_news,
)

logger = logging.getLogger(__name__)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data and capital flow",
        "tools": [
            "get_stock_data",
            "get_capital_flow"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "A-share news and announcements",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macro indicators (currently unavailable in local mode)",
        "tools": [
            "get_macro_indicators",
        ]
    },
    "prediction_markets": {
        "description": "Prediction markets (currently unavailable in local mode)",
        "tools": [
            "get_prediction_markets",
        ]
    }
}

VENDOR_LIST = [
    "local_db",
    "china_news",
    "local_news_api",
]

# Categories that degrade gracefully when no vendor can serve them.
OPTIONAL_CATEGORIES = {"macro_data", "prediction_markets"}

# Mapping of methods to vendor implementations (local sources only).
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "local_db": get_local_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "local_db": get_local_indicators,
    },
    # fundamental_data
    "get_fundamentals": {
        "local_db": get_local_fundamentals,
    },
    "get_balance_sheet": {
        "local_db": get_local_balance_sheet,
    },
    "get_cashflow": {
        "local_db": get_local_cashflow,
    },
    "get_income_statement": {
        "local_db": get_local_income_statement,
    },
    # news_data
    "get_news": {
        "local_db": get_local_news,
        "china_news": get_china_stock_news,
        "local_news_api": get_local_news_api,
    },
    "get_global_news": {
        "local_db": get_local_global_news,
        "china_news": get_china_global_news,
        "local_news_api": get_local_global_news_api,
    },
    "get_insider_transactions": {
        # No local source available — gracefully unavailable
    },
    # capital_flow (A-share only)
    "get_capital_flow": {
        "local_db": get_local_capital_flow,
    },
    # macro_data and prediction_markets: no local vendors available
    "get_macro_indicators": {},
    "get_prediction_markets": {},
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    all_available_vendors = list(VENDOR_METHODS[method].keys())

    # The configured vendor list IS the chain: we do NOT silently fall back to
    # vendors the user did not choose. For multi-vendor fallback, list them in
    # order, e.g. data_vendors="china_news,local_db".
    # The "default" sentinel (no explicit config) uses all available vendors.
    explicit = [v for v in primary_vendors if v and v != "default"]
    if explicit:
        vendor_chain = [v for v in explicit if v in VENDOR_METHODS[method]]
        if not vendor_chain:
            raise ValueError(
                f"Configured vendor(s) {explicit} not available for '{method}'. "
                f"Available: {all_available_vendors}."
            )
    else:
        vendor_chain = all_available_vendors

    # If no vendors are configured at all (e.g. get_macro_indicators with no local source),
    # return a clean unavailable sentinel.
    if not vendor_chain:
        if category in OPTIONAL_CATEGORIES:
            return (
                f"DATA_UNAVAILABLE: {category} is not available in local A-share mode. "
                f"No Chinese data source is configured for this category. Proceed without it."
            )
        raise RuntimeError(f"No vendor available for '{method}' in local A-share mode")

    last_no_data: NoMarketDataError | None = None
    first_error: Exception | None = None
    for vendor in vendor_chain:
        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except VendorRateLimitError:
            logger.warning("Vendor %r rate-limited for %s; trying next vendor.", vendor, method)
            continue
        except VendorNotConfiguredError as e:
            logger.warning("Vendor %r not configured for %s; trying next vendor.", vendor, method)
            if first_error is None:
                first_error = e
            continue
        except NoMarketDataError as e:
            last_no_data = e
            continue
        except Exception as e:
            logger.warning("Vendor %r failed for %s: %s", vendor, method, e)
            if first_error is None:
                first_error = e
            continue

    # If any vendor reported "no data", the symbol is genuinely unavailable.
    if last_no_data is not None:
        if first_error is not None:
            logger.warning(
                "Returning NO_DATA for %s, but a vendor errored earlier: %s",
                method, first_error,
            )
        sym = last_no_data.symbol
        canonical = last_no_data.canonical
        resolved = "" if canonical == sym else f" (resolved to '{canonical}')"
        reason = f" ({last_no_data.detail})" if last_no_data.detail else ""
        return (
            f"NO_DATA_AVAILABLE: No usable market data for '{sym}'{resolved} from "
            f"any configured vendor{reason}. The symbol may be invalid, delisted, "
            f"not covered, or the vendor returned stale data. Do not estimate or "
            f"fabricate values — report that data is unavailable for this symbol."
        )

    if first_error is not None:
        if category in OPTIONAL_CATEGORIES:
            logger.warning("Optional %s unavailable for %s: %s", category, method, first_error)
            return (
                f"DATA_UNAVAILABLE: optional {category} could not be retrieved "
                f"({first_error}). Proceed without it; do not fabricate values."
            )
        raise first_error

    raise RuntimeError(f"No available vendor for '{method}'")
