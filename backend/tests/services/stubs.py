"""Test doubles shared by the service and API suites."""

from __future__ import annotations

from app.market import MarketDataSource, PriceCache


class StubDataSource(MarketDataSource):
    """A `MarketDataSource` that records calls instead of generating prices.

    Prices therefore stay exactly as the test seeded them in the cache.
    """

    def __init__(self, price_cache: PriceCache) -> None:
        self.cache = price_cache
        self.tickers: list[str] = []
        self.started_with: list[str] | None = None
        self.added: list[str] = []
        self.removed: list[str] = []
        self.stopped = False

    async def start(self, tickers: list[str]) -> None:
        self.started_with = list(tickers)
        self.tickers = list(tickers)

    async def stop(self) -> None:
        self.stopped = True

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)
        if ticker not in self.tickers:
            self.tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)
        if ticker in self.tickers:
            self.tickers.remove(ticker)
        self.cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self.tickers)
