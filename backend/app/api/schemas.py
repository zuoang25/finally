"""Request bodies for the mutating endpoints.

Response shapes are built by the service layer as plain dicts so they match
CONTRACTS.md section 4 byte for byte.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol; upper-cased server-side")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]


class ChatRequest(BaseModel):
    message: str
