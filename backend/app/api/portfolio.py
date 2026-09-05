"""Portfolio endpoints (CONTRACTS.md sections 4.5-4.7).

These handlers are plain `def`, so FastAPI runs them in a threadpool and the
synchronous SQLite calls never block the event loop.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import DEFAULT_USER_ID, PortfolioServiceDep
from app.api.schemas import TradeRequest
from app.db import list_snapshots
from app.services.common import round_money

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio(service: PortfolioServiceDep) -> dict[str, Any]:
    return service.get_portfolio(user_id=DEFAULT_USER_ID)


@router.post("/trade")
def execute_trade(body: TradeRequest, service: PortfolioServiceDep) -> dict[str, Any]:
    """Market order, instant fill at the cached price.

    400 on a bad request or rejected fill, 503 when no price is available.
    """
    trade = service.execute_trade(
        ticker=body.ticker,
        side=body.side,
        quantity=body.quantity,
        user_id=DEFAULT_USER_ID,
    )
    return {"trade": trade, "portfolio": service.get_portfolio(user_id=DEFAULT_USER_ID)}


@router.get("/history")
def get_history(limit: int = Query(default=500, ge=1, le=5000)) -> dict[str, Any]:
    """Portfolio value snapshots, oldest first."""
    snapshots = list_snapshots(limit=limit, user_id=DEFAULT_USER_ID)
    return {
        "snapshots": [
            {"total_value": round_money(row.total_value), "recorded_at": row.recorded_at}
            for row in snapshots
        ]
    }
