"""Structural interfaces the LLM layer depends on.

The Backend API Engineer's concrete services satisfy these `Protocol`s
structurally -- the LLM package never imports them. See
`planning/CONTRACTS.md` section 5.1.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PortfolioServiceProtocol(Protocol):
    """Synchronous portfolio operations (SQLite-backed, safe in a worker thread)."""

    def get_portfolio(self, user_id: str = "default") -> dict:
        """Return the CONTRACTS.md section 4.5 portfolio payload."""
        ...

    def execute_trade(
        self, ticker: str, side: str, quantity: float, user_id: str = "default"
    ) -> dict:
        """Fill a market order and return the section 4.6 ``trade`` object.

        Raises `app.db.DbError` subclasses, or `ValueError` when no price is
        available for the ticker.
        """
        ...


@runtime_checkable
class WatchlistServiceProtocol(Protocol):
    """Asynchronous watchlist operations (they touch the market data source)."""

    async def get_watchlist(self, user_id: str = "default") -> list[dict]:
        """Return the CONTRACTS.md section 4.2 ticker items."""
        ...

    async def add_ticker(self, ticker: str, user_id: str = "default") -> dict:
        """Add a ticker; raises `DuplicateTickerError` or `ValueError` on a bad symbol."""
        ...

    async def remove_ticker(self, ticker: str, user_id: str = "default") -> bool:
        """Remove a ticker; returns False when it was not present."""
        ...
