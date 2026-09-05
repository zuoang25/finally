"""System endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import MarketDataSourceDep, SettingsDep

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(settings: SettingsDep, source: MarketDataSourceDep) -> dict[str, Any]:
    """Liveness probe used by Docker and the start scripts."""
    return {
        "status": "ok",
        "market_data_source": settings.market_data_source_name,
        "llm_mock": settings.llm_mock,
        "tickers_tracked": len(source.get_tickers()),
    }
