"""Tests for portfolio snapshot repository functions."""

from app.db.repositories import list_snapshots, record_snapshot


class TestSnapshots:
    def test_record_snapshot(self, isolated_db):
        row = record_snapshot(10000.0)
        assert row.total_value == 10000.0
        assert row.recorded_at

    def test_list_snapshots_oldest_first(self, isolated_db):
        record_snapshot(10000.0)
        record_snapshot(10500.0)
        record_snapshot(9800.0)
        values = [r.total_value for r in list_snapshots()]
        assert values == [10000.0, 10500.0, 9800.0]

    def test_list_snapshots_respects_limit(self, isolated_db):
        for i in range(5):
            record_snapshot(float(i))
        assert len(list_snapshots(limit=3)) == 3

    def test_snapshot_row_to_dict_keys(self, isolated_db):
        row = record_snapshot(10000.0)
        assert set(row.to_dict().keys()) == {"id", "user_id", "total_value", "recorded_at"}
