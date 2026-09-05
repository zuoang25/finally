"""Fixtures for the service-layer tests: a temp database and a fixed cache."""

import pytest

from app.db.connection import init_db
from app.market import PriceCache
from app.services import PortfolioService, WatchlistService
from tests.services.stubs import StubDataSource

# Deterministic (previous, latest) pairs; the seeded tickers' session opens come
# from app.market.seed_prices.SEED_PRICES (AAPL 190.00, MSFT 420.00, ...).
PRICES = {
    "AAPL": (190.42, 195.00),
    "MSFT": (420.00, 400.00),
    "NVDA": (800.00, 820.50),
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))
    init_db()
    yield db_file


@pytest.fixture
def price_cache() -> PriceCache:
    cache = PriceCache()
    for ticker, (previous, latest) in PRICES.items():
        cache.update(ticker, previous)
        cache.update(ticker, latest)
    return cache


@pytest.fixture
def data_source(price_cache: PriceCache) -> StubDataSource:
    return StubDataSource(price_cache)


@pytest.fixture
def portfolio_service(price_cache: PriceCache) -> PortfolioService:
    return PortfolioService(price_cache)


@pytest.fixture
def watchlist_service(price_cache: PriceCache, data_source: StubDataSource) -> WatchlistService:
    return WatchlistService(price_cache, data_source)
