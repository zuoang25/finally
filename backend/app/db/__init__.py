"""FinAlly database layer -- public surface.

Stdlib `sqlite3`-backed persistence for the user profile, watchlist,
positions, trades, portfolio snapshots and chat history. See
`planning/CONTRACTS.md` section 3 for the authoritative contract.
"""

from app.db.connection import get_connection, get_db_path, get_project_root, init_db
from app.db.exceptions import (
    DbError,
    DuplicateTickerError,
    InsufficientFundsError,
    InsufficientSharesError,
    PositionNotFoundError,
)
from app.db.models import ChatRow, PositionRow, SnapshotRow, TradeRow, WatchlistRow
from app.db.repositories import (
    add_chat_message,
    add_watchlist_ticker,
    apply_trade,
    delete_position,
    get_cash_balance,
    get_position,
    list_chat_messages,
    list_positions,
    list_snapshots,
    list_trades,
    list_watchlist,
    record_snapshot,
    record_trade,
    remove_watchlist_ticker,
    set_cash_balance,
    upsert_position,
    utcnow_iso,
)

__all__ = [
    # connection
    "get_connection",
    "get_db_path",
    "get_project_root",
    "init_db",
    # exceptions
    "DbError",
    "DuplicateTickerError",
    "InsufficientFundsError",
    "InsufficientSharesError",
    "PositionNotFoundError",
    # row types
    "ChatRow",
    "PositionRow",
    "SnapshotRow",
    "TradeRow",
    "WatchlistRow",
    # profile
    "get_cash_balance",
    "set_cash_balance",
    # watchlist
    "list_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    # positions
    "list_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    # trades
    "record_trade",
    "list_trades",
    # snapshots
    "record_snapshot",
    "list_snapshots",
    # chat
    "add_chat_message",
    "list_chat_messages",
    # atomic trade application
    "apply_trade",
    # helpers
    "utcnow_iso",
]
