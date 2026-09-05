"""Watchlist endpoints (CONTRACTS.md sections 4.2-4.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import DEFAULT_USER_ID, WatchlistServiceDep
from app.api.schemas import WatchlistAddRequest

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def get_watchlist(service: WatchlistServiceDep) -> dict[str, Any]:
    tickers = await service.get_watchlist(user_id=DEFAULT_USER_ID)
    return {"tickers": tickers}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_ticker(body: WatchlistAddRequest, service: WatchlistServiceDep) -> dict[str, Any]:
    """Add a ticker. 400 invalid symbol, 409 already watched."""
    return await service.add_ticker(body.ticker, user_id=DEFAULT_USER_ID)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ticker(ticker: str, service: WatchlistServiceDep) -> Response:
    """Remove a ticker. 400 invalid symbol, 404 when it is not watched."""
    removed = await service.remove_ticker(ticker, user_id=DEFAULT_USER_ID)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker.strip().upper()} is not on the watchlist",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
