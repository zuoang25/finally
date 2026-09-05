"""SQLite connection management and lazy database initialization.

Every repository function opens its own connection via `get_connection()` and
closes it when done -- connections are never shared across threads. The DB
path is resolved from the `FINALLY_DB_PATH` environment variable on every
call (not cached at import time) so tests can point it at a temp file per
test run.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_project_root() -> Path:
    """The project root, i.e. the parent of `backend/`."""
    # this file: backend/app/db/connection.py
    return Path(__file__).resolve().parents[3]


def get_db_path() -> Path:
    """Resolve the SQLite database path from `FINALLY_DB_PATH`.

    Relative paths are resolved against the project root. Defaults to
    `db/finally.db`.
    """
    raw = os.environ.get("FINALLY_DB_PATH", "db/finally.db")
    path = Path(raw)
    if not path.is_absolute():
        path = get_project_root() / path
    return path


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a new SQLite connection configured per project conventions.

    A fresh connection is expected per call/thread; callers are responsible
    for closing it (typically via a `try`/`finally`).
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Idempotent database initialization.

    Creates the parent directory, applies `schema.sql`, and seeds default
    data if `users_profile` is empty. Safe to call on every startup.
    """
    # Import here (not at module scope) to avoid a circular import, since
    # seed.py does not need anything from this module besides a connection.
    from app.db.seed import seed_default_data

    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(path)
    try:
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()

        seed_default_data(conn)
        conn.commit()
    finally:
        conn.close()
