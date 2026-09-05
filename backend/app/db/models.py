"""Frozen row dataclasses returned by the repository layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WatchlistRow:
    id: str
    user_id: str
    ticker: str
    added_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "added_at": self.added_at,
        }


@dataclass(frozen=True, slots=True)
class PositionRow:
    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class TradeRow:
    id: str
    user_id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "executed_at": self.executed_at,
        }


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    id: str
    user_id: str
    total_value: float
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total_value": self.total_value,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class ChatRow:
    id: str
    user_id: str
    role: str
    content: str
    actions: list[dict[str, Any]] | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "actions": self.actions,
            "created_at": self.created_at,
        }
