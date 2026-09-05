"""Exception hierarchy for the database layer.

Every message is human-readable and safe to surface directly as an HTTP 400
`detail` or inline in a chat response.
"""

from __future__ import annotations


class DbError(Exception):
    """Base class for all database-layer errors."""


class DuplicateTickerError(DbError):
    """Raised when adding a ticker already present on the user's watchlist."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"{ticker} is already on the watchlist")


class InsufficientFundsError(DbError):
    """Raised when a buy would require more cash than the user has."""

    def __init__(self, needed: float, have: float):
        self.needed = needed
        self.have = have
        super().__init__(f"Insufficient cash: need ${needed:.2f}, have ${have:.2f}")


class InsufficientSharesError(DbError):
    """Raised when a sell would require more shares than the user holds."""

    def __init__(self, ticker: str, needed: float, have: float):
        self.ticker = ticker
        self.needed = needed
        self.have = have
        super().__init__(f"Insufficient shares of {ticker}: need {needed:g}, have {have:g}")


class PositionNotFoundError(DbError):
    """Raised when an operation requires a position that does not exist."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No position found for {ticker}")
