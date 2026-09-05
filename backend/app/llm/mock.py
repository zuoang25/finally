"""Deterministic offline assistant used when `LLM_MOCK=true`.

The behaviour table is frozen in CONTRACTS.md section 5.3 -- the E2E suite
asserts on these exact message prefixes. Mock responses are returned as a
normal `AssistantResponse` and flow through the real execution path, so a mock
buy with insufficient cash still yields a `failed` action.
"""

import re
from collections.abc import Sequence
from typing import Any

from app.llm.schemas import AssistantResponse, Trade, WatchlistChange
from app.market.seed_prices import SEED_PRICES

_TOKEN_RE = re.compile(r"\b[A-Za-z]{1,5}\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def known_tickers(watchlist: Sequence[dict[str, Any]]) -> set[str]:
    """Watchlist tickers union the simulator's seed universe."""
    tickers = {str(item.get("ticker", "")).strip().upper() for item in watchlist}
    tickers.discard("")
    return tickers | set(SEED_PRICES)


def find_ticker(message: str, tickers: set[str]) -> str | None:
    """First standalone 1-5 letter token that is a known ticker."""
    for match in _TOKEN_RE.finditer(message):
        candidate = match.group(0).upper()
        if candidate in tickers:
            return candidate
    return None


def find_quantity(message: str) -> float | None:
    """First number in the message."""
    match = _NUMBER_RE.search(message)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:  # pragma: no cover - regex guarantees a valid float
        return None


def _fmt_qty(quantity: float) -> str:
    text = f"{quantity:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def build_mock_response(
    message: str,
    portfolio: dict[str, Any],
    watchlist: Sequence[dict[str, Any]],
) -> AssistantResponse:
    lowered = message.lower()
    tickers = known_tickers(watchlist)
    ticker = find_ticker(message, tickers)
    quantity = find_quantity(message)

    if "buy" in lowered and ticker and quantity is not None:
        return AssistantResponse(
            message=f"Executed: bought {_fmt_qty(quantity)} {ticker}.",
            trades=[Trade(ticker=ticker, side="buy", quantity=quantity)],
        )
    if "sell" in lowered and ticker and quantity is not None:
        return AssistantResponse(
            message=f"Executed: sold {_fmt_qty(quantity)} {ticker}.",
            trades=[Trade(ticker=ticker, side="sell", quantity=quantity)],
        )
    if "add" in lowered and ticker:
        return AssistantResponse(
            message=f"Added {ticker} to the watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )
    if "remove" in lowered and ticker:
        return AssistantResponse(
            message=f"Removed {ticker} from the watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    cash = portfolio.get("cash_balance") or 0.0
    count = len(portfolio.get("positions") or [])
    return AssistantResponse(
        message=(
            f"MOCK: cash ${float(cash):,.2f} across {count} position"
            f"{'' if count == 1 else 's'}. Ask me to buy, sell, add or remove a ticker."
        )
    )
