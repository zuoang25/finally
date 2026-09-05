"""Fixtures for the db test suite.

Every test gets its own SQLite file under pytest's `tmp_path`, pointed at via
`FINALLY_DB_PATH` -- the real `db/finally.db` is never touched.
"""

import pytest

from app.db.connection import init_db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))
    init_db()
    yield db_file
