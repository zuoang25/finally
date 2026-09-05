"""Watchlist reads/writes and day-change computation (CONTRACTS.md section 4.2).

This service owns the **session-open map**: the reference price each ticker's
day change is measured against. An entry is recorded the first time a price is
observed for a ticker; `SEED_PRICES` is preferred when the ticker is one of the
known seeds, so the day change reflects movement since the process started
rather than since the first API call.
"""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool

from app.db import (
    add_watchlist_ticker,
    get_position,
    list_watchlist,
    remove_watchlist_ticker,
)
from app.market import MarketDataSource, PriceCache
from app.market.seed_prices import SEED_PRICES
from app.services.common import normalize_ticker, round_money, round_percent

DEFAULT_USER_ID = "default"


class WatchlistService:
    """Watchlist CRUD kept in step with the market data source."""

    def __init__(self, price_cache: PriceCache, market_data_source: MarketDataSource) -> None:
        self._cache = price_cache
        self._source = market_data_source
        self._session_opens: dict[str, float] = {}

    # -- session opens -----------------------------------------------------

    def session_open(self, ticker: str, current_price: float) -> float:
        """The day's reference price for `ticker`, recording it on first sight."""
        open_price = self._session_opens.get(ticker)
        if open_price is None:
            open_price = SEED_PRICES.get(ticker, current_price)
            self._session_opens[ticker] = open_price
        return open_price

    def build_item(self, ticker: str, added_at: str) -> dict[str, Any]:
        """One section 4.2 watchlist item for `ticker`."""
        update = self._cache.get(ticker)
        if update is None:
            return {
                "ticker": ticker,
                "price": None,
                "previous_price": None,
                "open_price": None,
                "change": None,
                "change_percent": None,
                "direction": "flat",
                "added_at": added_at,
            }

        open_price = self.session_open(ticker, update.price)
        change = update.price - open_price
        change_percent = (change / open_price * 100) if open_price else 0.0
        return {
            "ticker": ticker,
            "price": round_money(update.price),
            "previous_price": round_money(update.previous_price),
            "open_price": round_money(open_price),
            # `change` / `change_percent` here are the DAY change against the
            # session open, not the tick-over-tick values on PriceUpdate.
            "change": round_money(change),
            "change_percent": round_percent(change_percent),
            "direction": update.direction,
            "added_at": added_at,
        }

    # -- operations --------------------------------------------------------

    async def get_watchlist(self, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
        """Every watched ticker with live prices, ordered by `added_at` ascending."""
        rows = await run_in_threadpool(list_watchlist, user_id=user_id)
        return [self.build_item(row.ticker, row.added_at) for row in rows]

    async def add_ticker(self, ticker: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        """Add a ticker and start streaming prices for it.

        Raises `InvalidTickerError` on a bad symbol and `DuplicateTickerError`
        when it is already watched.
        """
        symbol = normalize_ticker(ticker)
        row = await run_in_threadpool(add_watchlist_ticker, symbol, user_id=user_id)
        await self._source.add_ticker(symbol)
        return self.build_item(symbol, row.added_at)

    async def remove_ticker(self, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
        """Remove a ticker; returns `False` when it was not on the watchlist.

        Pricing continues for a removed ticker the user still holds a position
        in, so the portfolio keeps valuing correctly.
        """
        symbol = normalize_ticker(ticker)
        removed = await run_in_threadpool(remove_watchlist_ticker, symbol, user_id=user_id)
        if not removed:
            return False
        position = await run_in_threadpool(get_position, symbol, user_id=user_id)
        if position is None:
            await self._source.remove_ticker(symbol)
        return True
