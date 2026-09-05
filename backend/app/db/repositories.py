"""Repository functions -- the public data-access surface of `app.db`.

All functions are synchronous and open/close their own SQLite connection
(never shared across threads, per project convention). Ids are `uuid4().hex`
strings; timestamps are ISO-8601 UTC strings with a `Z` suffix produced by
`utcnow_iso()`.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from app.db.connection import get_connection
from app.db.exceptions import (
    DuplicateTickerError,
    InsufficientFundsError,
    InsufficientSharesError,
)
from app.db.models import ChatRow, PositionRow, SnapshotRow, TradeRow, WatchlistRow

_POSITION_TOLERANCE = 1e-9

DEFAULT_USER_ID = "default"


def utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 string with a `Z` suffix, ms precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        return row["cash_balance"] if row is not None else 0.0
    finally:
        conn.close()


def set_cash_balance(balance: float, user_id: str = DEFAULT_USER_ID) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET cash_balance = excluded.cash_balance",
            (user_id, balance, utcnow_iso()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# watchlist
# ---------------------------------------------------------------------------


def list_watchlist(user_id: str = DEFAULT_USER_ID) -> list[WatchlistRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist "
            "WHERE user_id = ? ORDER BY added_at ASC, rowid ASC",
            (user_id,),
        ).fetchall()
        return [WatchlistRow(**dict(row)) for row in rows]
    finally:
        conn.close()


def add_watchlist_ticker(ticker: str, user_id: str = DEFAULT_USER_ID) -> WatchlistRow:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        if existing is not None:
            raise DuplicateTickerError(ticker)

        row_id = new_id()
        added_at = utcnow_iso()
        try:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (row_id, user_id, ticker, added_at),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTickerError(ticker) from exc
        conn.commit()
        return WatchlistRow(id=row_id, user_id=user_id, ticker=ticker, added_at=added_at)
    finally:
        conn.close()


def remove_watchlist_ticker(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------


def list_positions(user_id: str = DEFAULT_USER_ID) -> list[PositionRow]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker ASC",
            (user_id,),
        ).fetchall()
        return [PositionRow(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> PositionRow | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        return PositionRow(**dict(row)) if row is not None else None
    finally:
        conn.close()


def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = DEFAULT_USER_ID
) -> PositionRow:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        updated_at = utcnow_iso()
        if existing is not None:
            row_id = existing["id"]
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
                (quantity, avg_cost, updated_at, row_id),
            )
        else:
            row_id = new_id()
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row_id, user_id, ticker, quantity, avg_cost, updated_at),
            )
        conn.commit()
        return PositionRow(
            id=row_id,
            user_id=user_id,
            ticker=ticker,
            quantity=quantity,
            avg_cost=avg_cost,
            updated_at=updated_at,
        )
    finally:
        conn.close()


def delete_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# trades
# ---------------------------------------------------------------------------


def record_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID
) -> TradeRow:
    conn = get_connection()
    try:
        row_id = new_id()
        executed_at = utcnow_iso()
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row_id, user_id, ticker, side, quantity, price, executed_at),
        )
        conn.commit()
        return TradeRow(
            id=row_id,
            user_id=user_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=executed_at,
        )
    finally:
        conn.close()


def list_trades(limit: int = 100, user_id: str = DEFAULT_USER_ID) -> list[TradeRow]:
    """Trade history, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, user_id, ticker, side, quantity, price, executed_at FROM trades "
            "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [TradeRow(**dict(row)) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------


def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> SnapshotRow:
    conn = get_connection()
    try:
        row_id = new_id()
        recorded_at = utcnow_iso()
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (row_id, user_id, total_value, recorded_at),
        )
        conn.commit()
        return SnapshotRow(
            id=row_id, user_id=user_id, total_value=total_value, recorded_at=recorded_at
        )
    finally:
        conn.close()


def list_snapshots(limit: int = 500, user_id: str = DEFAULT_USER_ID) -> list[SnapshotRow]:
    """Portfolio value snapshots, oldest first (chart-ready, left to right)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, user_id, total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at ASC, rowid ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [SnapshotRow(**dict(row)) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


def add_chat_message(
    role: str,
    content: str,
    actions: list[dict] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> ChatRow:
    conn = get_connection()
    try:
        row_id = new_id()
        created_at = utcnow_iso()
        actions_json = json.dumps(actions) if actions is not None else None
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, user_id, role, content, actions_json, created_at),
        )
        conn.commit()
        return ChatRow(
            id=row_id,
            user_id=user_id,
            role=role,
            content=content,
            actions=actions,
            created_at=created_at,
        )
    finally:
        conn.close()


def list_chat_messages(limit: int = 50, user_id: str = DEFAULT_USER_ID) -> list[ChatRow]:
    """Conversation history, oldest first (render order)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, user_id, role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at ASC, rowid ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            raw_actions = data.pop("actions")
            actions = json.loads(raw_actions) if raw_actions is not None else None
            result.append(ChatRow(actions=actions, **data))
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# atomic trade application
# ---------------------------------------------------------------------------


def apply_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID
) -> TradeRow:
    """Validate and apply a trade atomically.

    Updates cash, upserts or deletes the position, and inserts the trade row
    all within a single transaction. Raises `InsufficientFundsError` /
    `InsufficientSharesError` and rolls back cleanly on failure. This is the
    only place cash and positions change together.
    """
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    if side not in ("buy", "sell"):
        raise ValueError('side must be "buy" or "sell"')

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            profile_row = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
            ).fetchone()
            cash_balance = profile_row["cash_balance"] if profile_row is not None else 0.0

            pos_row = conn.execute(
                "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            ).fetchone()

            now = utcnow_iso()

            if side == "buy":
                cost = quantity * price
                if cost > cash_balance + _POSITION_TOLERANCE:
                    raise InsufficientFundsError(cost, cash_balance)

                if pos_row is None:
                    new_qty = quantity
                    new_avg_cost = round(price, 6)
                    conn.execute(
                        "INSERT INTO positions "
                        "(id, user_id, ticker, quantity, avg_cost, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (new_id(), user_id, ticker, new_qty, new_avg_cost, now),
                    )
                else:
                    old_qty = pos_row["quantity"]
                    old_avg = pos_row["avg_cost"]
                    new_qty = old_qty + quantity
                    new_avg_cost = round((old_qty * old_avg + quantity * price) / new_qty, 6)
                    conn.execute(
                        "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                        "WHERE id = ?",
                        (new_qty, new_avg_cost, now, pos_row["id"]),
                    )

                new_cash = cash_balance - cost
            else:  # sell
                if pos_row is None:
                    raise InsufficientSharesError(ticker, quantity, 0.0)

                old_qty = pos_row["quantity"]
                if quantity > old_qty + _POSITION_TOLERANCE:
                    raise InsufficientSharesError(ticker, quantity, old_qty)

                new_qty = old_qty - quantity
                if new_qty <= _POSITION_TOLERANCE:
                    conn.execute("DELETE FROM positions WHERE id = ?", (pos_row["id"],))
                else:
                    conn.execute(
                        "UPDATE positions SET quantity = ?, updated_at = ? WHERE id = ?",
                        (new_qty, now, pos_row["id"]),
                    )

                new_cash = cash_balance + quantity * price

            conn.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET cash_balance = excluded.cash_balance",
                (user_id, new_cash, now),
            )

            trade_id = new_id()
            conn.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trade_id, user_id, ticker, side, quantity, price, now),
            )

            conn.commit()
            return TradeRow(
                id=trade_id,
                user_id=user_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=price,
                executed_at=now,
            )
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()
