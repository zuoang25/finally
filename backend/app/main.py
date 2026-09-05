"""FastAPI application assembly for FinAlly.

`create_app()` wires the price cache, market data source, services and routers
together; the lifespan initialises the database, starts the market data source
on the persisted watchlist, runs the periodic portfolio-snapshot task, and
shuts both down cleanly. `app` at the bottom is the uvicorn target
(`uv run uvicorn app.main:app`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api import chat_router, health_router, portfolio_router, watchlist_router
from app.api.errors import register_exception_handlers
from app.config import Settings, load_settings
from app.db import init_db, list_positions, list_watchlist
from app.market import (
    MarketDataSource,
    PriceCache,
    create_market_data_source,
    create_stream_router,
)
from app.services import PortfolioService, WatchlistService

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"
SNAPSHOT_INTERVAL_SECONDS = 30.0
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _startup_tickers(user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Watchlist tickers plus any ticker the user still holds a position in."""
    tickers = [row.ticker for row in list_watchlist(user_id=user_id)]
    seen = set(tickers)
    for position in list_positions(user_id=user_id):
        if position.ticker not in seen:
            seen.add(position.ticker)
            tickers.append(position.ticker)
    return tickers


async def _record_snapshot(portfolio_service: PortfolioService) -> None:
    """Append one `portfolio_snapshots` row; a failure must not stop the app."""
    try:
        await run_in_threadpool(portfolio_service.record_snapshot, user_id=DEFAULT_USER_ID)
    except Exception:
        logger.exception("Portfolio snapshot failed")


async def _snapshot_loop(portfolio_service: PortfolioService, interval: float) -> None:
    """Append a `portfolio_snapshots` row every `interval` seconds.

    Sleeps first: the startup snapshot is taken by the lifespan itself, so that
    a short-lived process still leaves the P&L chart with a starting point.
    """
    while True:
        await asyncio.sleep(interval)
        await _record_snapshot(portfolio_service)


def _build_chat_service(
    portfolio_service: PortfolioService,
    watchlist_service: WatchlistService,
    settings: Settings,
) -> Any | None:
    """Construct `app.llm.ChatService`, tolerating an absent/broken LLM module.

    The chat module is developed independently; the rest of the API must start
    and serve regardless of its state. `/api/chat` returns 503 when this is None.

    `mock` is passed explicitly so the app's own `Settings` decide mock mode
    rather than the ambient `LLM_MOCK` variable — an injected
    `Settings(llm_mock=True)` then guarantees no provider call.
    """
    try:
        from app.llm import ChatService
    except Exception as exc:  # noqa: BLE001 - module may not exist yet
        logger.warning("Chat service unavailable (import failed): %s", exc)
        return None
    try:
        return ChatService(
            portfolio_service=portfolio_service,
            watchlist_service=watchlist_service,
            mock=settings.llm_mock,
        )
    except Exception:
        logger.exception("Chat service unavailable (construction failed)")
        return None


def _scoped_stream_router(price_cache: PriceCache) -> APIRouter:
    """The SSE route bound to `price_cache`.

    `create_stream_router` registers onto a module-level router, so a second
    call would leave the app holding a stale route bound to the first cache.
    Taking only the route this call appended keeps each app self-contained.
    """
    registered = create_stream_router(price_cache)
    scoped = APIRouter()
    scoped.routes.append(registered.routes[-1])
    return scoped


def _register_static(app: FastAPI, static_dir: Path | None) -> None:
    """Serve the Next.js export at `/` with an SPA fallback.

    Registered last so every API route wins the match. Unknown `/api/*` paths
    return a JSON 404 rather than the HTML shell.
    """

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa_fallback(full_path: str) -> Response:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

        if static_dir is None or not static_dir.is_dir():
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "finally-backend",
                    "detail": "Frontend static export not found; the API is served under /api.",
                }
            )

        root = static_dir.resolve()
        index = root / "index.html"
        if full_path:
            candidate = (root / full_path).resolve()
            # Never serve anything outside the static root.
            if candidate.is_relative_to(root):
                if candidate.is_file():
                    return FileResponse(candidate)
                nested_index = candidate / "index.html"
                if nested_index.is_file():
                    return FileResponse(nested_index)

        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def create_app(
    settings: Settings | None = None,
    price_cache: PriceCache | None = None,
    market_data_source: MarketDataSource | None = None,
    *,
    enable_snapshot_task: bool = True,
    snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
    static_dir: Path | None = STATIC_DIR,
) -> FastAPI:
    """Build the FastAPI app. Injectable pieces keep it testable."""
    resolved_settings = settings or load_settings()
    cache = price_cache if price_cache is not None else PriceCache()
    source = market_data_source or create_market_data_source(cache)
    portfolio_service = PortfolioService(cache)
    watchlist_service = WatchlistService(cache, source)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await run_in_threadpool(init_db)
        tickers = await run_in_threadpool(_startup_tickers)
        await source.start(tickers)
        app.state.chat_service = _build_chat_service(
            portfolio_service, watchlist_service, resolved_settings
        )

        snapshot_task: asyncio.Task[None] | None = None
        if enable_snapshot_task:
            await _record_snapshot(portfolio_service)
            snapshot_task = asyncio.create_task(
                _snapshot_loop(portfolio_service, snapshot_interval),
                name="portfolio-snapshots",
            )
        app.state.snapshot_task = snapshot_task

        try:
            yield
        finally:
            if snapshot_task is not None:
                snapshot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await snapshot_task
            await source.stop()

    app = FastAPI(
        title="FinAlly",
        description="AI trading workstation backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.settings = resolved_settings
    app.state.price_cache = cache
    app.state.market_data_source = source
    app.state.portfolio_service = portfolio_service
    app.state.watchlist_service = watchlist_service
    app.state.chat_service = None
    app.state.static_dir = static_dir

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(watchlist_router)
    app.include_router(portfolio_router)
    app.include_router(chat_router)
    app.include_router(_scoped_stream_router(cache))

    # Must be last: it matches every remaining path.
    _register_static(app, static_dir)

    return app


app = create_app()
