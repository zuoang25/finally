"""Tests for position repository functions."""

from app.db.repositories import delete_position, get_position, list_positions, upsert_position


class TestPositions:
    def test_upsert_creates_new_position(self, isolated_db):
        row = upsert_position("AAPL", 10.0, 190.0)
        assert row.ticker == "AAPL"
        assert row.quantity == 10.0
        assert row.avg_cost == 190.0
        assert row.updated_at

    def test_upsert_updates_existing_position(self, isolated_db):
        upsert_position("AAPL", 10.0, 190.0)
        row = upsert_position("AAPL", 15.0, 200.0)
        assert row.quantity == 15.0
        assert row.avg_cost == 200.0
        assert len(list_positions()) == 1

    def test_get_position_returns_none_when_absent(self, isolated_db):
        assert get_position("AAPL") is None

    def test_get_position_returns_row_when_present(self, isolated_db):
        upsert_position("AAPL", 10.0, 190.0)
        row = get_position("AAPL")
        assert row is not None
        assert row.ticker == "AAPL"
        assert row.quantity == 10.0

    def test_delete_position_removes_row(self, isolated_db):
        upsert_position("AAPL", 10.0, 190.0)
        delete_position("AAPL")
        assert get_position("AAPL") is None

    def test_delete_position_absent_is_noop(self, isolated_db):
        delete_position("AAPL")  # must not raise

    def test_list_positions_ordered_by_ticker(self, isolated_db):
        upsert_position("TSLA", 1.0, 250.0)
        upsert_position("AAPL", 1.0, 190.0)
        tickers = [r.ticker for r in list_positions()]
        assert tickers == ["AAPL", "TSLA"]

    def test_fractional_share_quantity(self, isolated_db):
        row = upsert_position("AAPL", 0.5, 190.0)
        assert row.quantity == 0.5

    def test_position_row_to_dict_keys(self, isolated_db):
        row = upsert_position("AAPL", 10.0, 190.0)
        assert set(row.to_dict().keys()) == {
            "id",
            "user_id",
            "ticker",
            "quantity",
            "avg_cost",
            "updated_at",
        }
