"""Tests for trade repository functions (record_trade / list_trades)."""

from app.db.repositories import list_trades, record_trade


class TestTrades:
    def test_record_trade(self, isolated_db):
        row = record_trade("AAPL", "buy", 10.0, 190.0)
        assert row.ticker == "AAPL"
        assert row.side == "buy"
        assert row.quantity == 10.0
        assert row.price == 190.0
        assert row.executed_at

    def test_list_trades_newest_first(self, isolated_db):
        record_trade("AAPL", "buy", 1.0, 190.0)
        record_trade("GOOGL", "buy", 1.0, 175.0)
        record_trade("MSFT", "buy", 1.0, 420.0)
        tickers = [r.ticker for r in list_trades()]
        assert tickers == ["MSFT", "GOOGL", "AAPL"]

    def test_list_trades_respects_limit(self, isolated_db):
        for _ in range(5):
            record_trade("AAPL", "buy", 1.0, 190.0)
        assert len(list_trades(limit=2)) == 2

    def test_trade_row_to_dict_keys(self, isolated_db):
        row = record_trade("AAPL", "buy", 1.0, 190.0)
        assert set(row.to_dict().keys()) == {
            "id",
            "user_id",
            "ticker",
            "side",
            "quantity",
            "price",
            "executed_at",
        }
