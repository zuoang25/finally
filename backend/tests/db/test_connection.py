"""Tests for connection.py: path resolution, connection setup, init_db."""

from app.db.connection import get_connection, get_db_path, get_project_root, init_db


class TestGetDbPath:
    def test_relative_path_resolves_against_project_root(self, monkeypatch):
        monkeypatch.setenv("FINALLY_DB_PATH", "db/finally.db")
        assert get_db_path() == get_project_root() / "db" / "finally.db"

    def test_absolute_path_passthrough(self, tmp_path, monkeypatch):
        target = tmp_path / "somewhere" / "finally.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(target))
        assert get_db_path() == target

    def test_default_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
        assert get_db_path() == get_project_root() / "db" / "finally.db"

    def test_project_root_is_parent_of_backend(self):
        root = get_project_root()
        assert (root / "backend").is_dir()


class TestGetConnection:
    def test_pragmas_applied(self, isolated_db):
        conn = get_connection()
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        finally:
            conn.close()

    def test_row_factory_is_sqlite_row(self, isolated_db):
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 AS one").fetchone()
            assert row["one"] == 1
        finally:
            conn.close()


class TestInitDb:
    def test_creates_all_tables(self, isolated_db):
        conn = get_connection()
        try:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        expected = {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }
        assert expected.issubset(tables)

    def test_idempotent_on_repeated_calls(self, isolated_db):
        # isolated_db already ran init_db() once.
        init_db()
        init_db()

        conn = get_connection()
        try:
            profile_count = conn.execute(
                "SELECT COUNT(*) AS n FROM users_profile"
            ).fetchone()["n"]
            watchlist_count = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
        finally:
            conn.close()

        assert profile_count == 1
        assert watchlist_count == 10

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "nested" / "dir" / "finally.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(nested))
        init_db()
        assert nested.exists()
