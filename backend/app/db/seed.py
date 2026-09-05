"""Default seed data applied to a freshly initialized database."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

# Matches app.market.seed_prices.SEED_PRICES / PLAN.md section 7.
DEFAULT_WATCHLIST_TICKERS: list[str] = [
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


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def seed_default_data(conn: sqlite3.Connection) -> None:
    """Seed the default user profile and watchlist.

    Idempotent: only seeds when `users_profile` is empty, so this is safe to
    call on every startup after the schema has been applied.
    """
    row = conn.execute("SELECT COUNT(*) AS n FROM users_profile").fetchone()
    if row["n"] > 0:
        return

    now = _utcnow_iso()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )
    for ticker in DEFAULT_WATCHLIST_TICKERS:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, DEFAULT_USER_ID, ticker, now),
        )
