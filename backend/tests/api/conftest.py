"""Fixtures for the API tests: a TestClient over an app with a temp database,
a pre-seeded price cache and a stub market data source.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.connection import init_db
from app.main import create_app
from app.market import PriceCache
from tests.services.stubs import StubDataSource

# (previous, latest) price pairs. Session opens come from SEED_PRICES, so AAPL
# shows a +5.00 day change and MSFT a -20.00 one.
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
def settings() -> Settings:
    return Settings(llm_mock=True)


@pytest.fixture
def app(settings, price_cache, data_source):
    return create_app(
        settings=settings,
        price_cache=price_cache,
        market_data_source=data_source,
        enable_snapshot_task=False,
        static_dir=None,
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
