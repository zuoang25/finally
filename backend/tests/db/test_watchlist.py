"""Tests for watchlist repository functions."""

import pytest

from app.db import DuplicateTickerError
from app.db.repositories import add_watchlist_ticker, list_watchlist, remove_watchlist_ticker


class TestWatchlist:
    def test_add_new_ticker(self, isolated_db):
        row = add_watchlist_ticker("PYPL")
        assert row.ticker == "PYPL"
        assert row.user_id == "default"
        assert row.id
        assert row.added_at

        tickers = [r.ticker for r in list_watchlist()]
        assert "PYPL" in tickers

    def test_add_duplicate_raises(self, isolated_db):
        add_watchlist_ticker("PYPL")
        with pytest.raises(DuplicateTickerError):
            add_watchlist_ticker("PYPL")

    def test_list_ordered_by_added_at_ascending(self, isolated_db):
        add_watchlist_ticker("PYPL")
        add_watchlist_ticker("SHOP")
        tickers = [r.ticker for r in list_watchlist()]
        # Seed tickers were added first (during init_db), so new ones land last.
        assert tickers[-2:] == ["PYPL", "SHOP"]

    def test_remove_existing_returns_true(self, isolated_db):
        assert remove_watchlist_ticker("AAPL") is True
        tickers = [r.ticker for r in list_watchlist()]
        assert "AAPL" not in tickers

    def test_remove_absent_returns_false(self, isolated_db):
        assert remove_watchlist_ticker("NOPE") is False

    def test_watchlist_row_to_dict_keys(self, isolated_db):
        row = add_watchlist_ticker("PYPL")
        assert set(row.to_dict().keys()) == {"id", "user_id", "ticker", "added_at"}

    def test_watchlist_is_scoped_per_user(self, isolated_db):
        add_watchlist_ticker("PYPL", user_id="alice")
        default_tickers = [r.ticker for r in list_watchlist()]
        alice_tickers = [r.ticker for r in list_watchlist(user_id="alice")]
        assert "PYPL" not in default_tickers
        assert alice_tickers == ["PYPL"]
