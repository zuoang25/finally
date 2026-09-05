"""Unit tests for `WatchlistService` (CONTRACTS.md sections 4.2-4.4)."""

import pytest

from app.db import DuplicateTickerError, apply_trade, list_watchlist
from app.services.common import InvalidTickerError


class TestGetWatchlist:
    async def test_seeded_watchlist_order_and_shape(self, watchlist_service):
        items = await watchlist_service.get_watchlist()

        assert [item["ticker"] for item in items] == [
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "NVDA",
            "META",
            "JPM",
            "V",
            "NFLX",
        ]
        assert set(items[0]) == {
            "ticker",
            "price",
            "previous_price",
            "open_price",
            "change",
            "change_percent",
            "direction",
            "added_at",
        }

    async def test_day_change_is_measured_against_the_session_open(self, watchlist_service):
        items = {item["ticker"]: item for item in await watchlist_service.get_watchlist()}

        aapl = items["AAPL"]
        assert aapl["price"] == 195.0
        assert aapl["previous_price"] == 190.42  # tick-over-tick, from the cache
        assert aapl["open_price"] == 190.0  # SEED_PRICES
        assert aapl["change"] == 5.0
        assert aapl["change_percent"] == pytest.approx(2.6316)
        assert aapl["direction"] == "up"

        msft = items["MSFT"]
        assert msft["change"] == -20.0
        assert msft["change_percent"] == pytest.approx(-4.7619)
        assert msft["direction"] == "down"

    async def test_ticker_without_a_price_is_null(self, watchlist_service):
        items = {item["ticker"]: item for item in await watchlist_service.get_watchlist()}

        googl = items["GOOGL"]
        assert googl["price"] is None
        assert googl["previous_price"] is None
        assert googl["open_price"] is None
        assert googl["change"] is None
        assert googl["change_percent"] is None
        assert googl["direction"] == "flat"
        assert googl["added_at"]

    async def test_session_open_is_fixed_after_the_first_observation(
        self, watchlist_service, price_cache
    ):
        await watchlist_service.get_watchlist()
        price_cache.update("AAPL", 200.0)

        items = {item["ticker"]: item for item in await watchlist_service.get_watchlist()}

        assert items["AAPL"]["open_price"] == 190.0
        assert items["AAPL"]["change"] == 10.0

    async def test_unknown_ticker_opens_at_its_first_observed_price(
        self, watchlist_service, price_cache
    ):
        price_cache.update("PYPL", 62.5)
        await watchlist_service.add_ticker("PYPL")
        price_cache.update("PYPL", 65.0)

        items = {item["ticker"]: item for item in await watchlist_service.get_watchlist()}

        assert items["PYPL"]["open_price"] == 62.5
        assert items["PYPL"]["change"] == 2.5


class TestAddTicker:
    async def test_adds_normalised_symbol_and_starts_pricing(
        self, watchlist_service, data_source
    ):
        item = await watchlist_service.add_ticker("  pypl ")

        assert item["ticker"] == "PYPL"
        assert item["price"] is None
        assert data_source.added == ["PYPL"]
        assert "PYPL" in [row.ticker for row in list_watchlist()]

    async def test_duplicate(self, watchlist_service, data_source):
        with pytest.raises(DuplicateTickerError):
            await watchlist_service.add_ticker("aapl")

        assert data_source.added == []

    @pytest.mark.parametrize("bad", ["", "  ", "123", "TOOLONGSYMBOL", "9AA"])
    async def test_invalid_symbol(self, watchlist_service, bad):
        with pytest.raises(InvalidTickerError):
            await watchlist_service.add_ticker(bad)


class TestRemoveTicker:
    async def test_removes_and_stops_pricing(self, watchlist_service, data_source):
        assert await watchlist_service.remove_ticker("aapl") is True

        assert data_source.removed == ["AAPL"]
        assert "AAPL" not in [row.ticker for row in list_watchlist()]

    async def test_missing_returns_false(self, watchlist_service, data_source):
        assert await watchlist_service.remove_ticker("PYPL") is False
        assert data_source.removed == []

    async def test_keeps_pricing_a_held_position(self, watchlist_service, data_source):
        apply_trade("AAPL", "buy", 1.0, 195.0)

        assert await watchlist_service.remove_ticker("AAPL") is True

        assert data_source.removed == []
        assert "AAPL" not in [row.ticker for row in list_watchlist()]

    async def test_invalid_symbol(self, watchlist_service):
        with pytest.raises(InvalidTickerError):
            await watchlist_service.remove_ticker("!!")
