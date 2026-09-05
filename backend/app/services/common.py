"""Shared validation helpers and service-level exceptions."""

from __future__ import annotations

import re

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")

MONEY_DP = 2
PERCENT_DP = 4
QUANTITY_DP = 6


class InvalidTickerError(ValueError):
    """Raised when a symbol does not look like a tradable ticker (HTTP 400)."""


class TradeValidationError(ValueError):
    """Raised for a malformed trade request, e.g. quantity <= 0 (HTTP 400)."""


class NoPriceError(ValueError):
    """Raised when no live price exists for a ticker yet (HTTP 503).

    Subclasses `ValueError` so it also satisfies the
    `PortfolioServiceProtocol` contract in CONTRACTS.md section 5.1.
    """


def normalize_ticker(ticker: str) -> str:
    """Upper-case and trim a symbol, validating it against `TICKER_PATTERN`."""
    symbol = (ticker or "").strip().upper()
    if not TICKER_PATTERN.match(symbol):
        raise InvalidTickerError(f"Invalid ticker symbol: {ticker!r}")
    return symbol


def round_money(value: float) -> float:
    return round(value, MONEY_DP)


def round_percent(value: float) -> float:
    return round(value, PERCENT_DP)


def round_quantity(value: float) -> float:
    return round(value, QUANTITY_DP)
