"""FastAPI dependencies resolving shared state off `app.state`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from app.config import Settings
from app.market import MarketDataSource, PriceCache
from app.services import PortfolioService, WatchlistService

DEFAULT_USER_ID = "default"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_data_source(request: Request) -> MarketDataSource:
    return request.app.state.market_data_source


def get_portfolio_service(request: Request) -> PortfolioService:
    return request.app.state.portfolio_service


def get_watchlist_service(request: Request) -> WatchlistService:
    return request.app.state.watchlist_service


def get_chat_service(request: Request) -> Any | None:
    """The `app.llm.ChatService`, or `None` when it could not be constructed."""
    return getattr(request.app.state, "chat_service", None)


SettingsDep = Annotated[Settings, Depends(get_settings)]
PriceCacheDep = Annotated[PriceCache, Depends(get_price_cache)]
MarketDataSourceDep = Annotated[MarketDataSource, Depends(get_market_data_source)]
PortfolioServiceDep = Annotated[PortfolioService, Depends(get_portfolio_service)]
WatchlistServiceDep = Annotated[WatchlistService, Depends(get_watchlist_service)]
ChatServiceDep = Annotated[Any, Depends(get_chat_service)]
