"""Tests for seed.py default data."""

from app.db.connection import get_connection
from app.db.repositories import get_cash_balance, list_watchlist
from app.db.seed import DEFAULT_CASH_BALANCE, DEFAULT_WATCHLIST_TICKERS, seed_default_data


class TestSeedData:
    def test_default_cash_balance(self, isolated_db):
        assert get_cash_balance() == DEFAULT_CASH_BALANCE

    def test_default_watchlist_tickers_and_order(self, isolated_db):
        tickers = [row.ticker for row in list_watchlist()]
        assert tickers == DEFAULT_WATCHLIST_TICKERS

    def test_seed_is_noop_once_users_profile_populated(self, isolated_db):
        conn = get_connection()
        try:
            seed_default_data(conn)
            conn.commit()
            profile_count = conn.execute(
                "SELECT COUNT(*) AS n FROM users_profile"
            ).fetchone()["n"]
            watchlist_count = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
        finally:
            conn.close()
        assert profile_count == 1
        assert watchlist_count == 10
