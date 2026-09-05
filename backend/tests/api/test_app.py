"""App assembly: startup tickers, the snapshot task, SSE wiring and shutdown."""

import asyncio
import json
from contextlib import suppress

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import Settings
from app.db import apply_trade, list_snapshots, remove_watchlist_ticker
from app.main import _snapshot_loop, _startup_tickers, create_app
from app.market import PriceCache
from app.services import PortfolioService
from tests.services.stubs import StubDataSource


def _app(price_cache, data_source, **kwargs):
    return create_app(
        settings=Settings(llm_mock=True),
        price_cache=price_cache,
        market_data_source=data_source,
        static_dir=None,
        **kwargs,
    )


class TestStartupTickers:
    def test_watchlist_plus_held_positions(self):
        apply_trade("PYPL", "buy", 1.0, 60.0)
        remove_watchlist_ticker("AAPL")

        tickers = _startup_tickers()

        assert "AAPL" not in tickers
        assert tickers[-1] == "PYPL"
        assert len(tickers) == 10

    def test_source_receives_them_on_startup(self, price_cache, data_source):
        apply_trade("PYPL", "buy", 1.0, 60.0)

        with TestClient(_app(price_cache, data_source, enable_snapshot_task=False)):
            pass

        assert "PYPL" in data_source.started_with


class TestSnapshotTask:
    def test_records_a_snapshot_on_startup(self, price_cache, data_source):
        with TestClient(_app(price_cache, data_source, snapshot_interval=30.0)):
            pass

        snapshots = list_snapshots()

        assert len(snapshots) >= 1
        assert snapshots[0].total_value == pytest.approx(10000.0)

    def test_disabled_records_nothing(self, price_cache, data_source):
        with TestClient(_app(price_cache, data_source, enable_snapshot_task=False)):
            pass

        assert list_snapshots() == []

    async def test_the_loop_keeps_appending(self, price_cache):
        task = asyncio.create_task(_snapshot_loop(PortfolioService(price_cache), 0.01))
        try:
            async with asyncio.timeout(5):
                while len(list_snapshots()) < 3:
                    await asyncio.sleep(0.01)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class TestShutdown:
    def test_stops_the_market_data_source(self, price_cache, data_source):
        with TestClient(_app(price_cache, data_source, snapshot_interval=0.01)) as client:
            assert client.get("/api/health").status_code == 200

        assert data_source.stopped is True


class TestStreamRouter:
    def test_route_is_mounted(self, app):
        assert "/api/stream/prices" in {route.path for route in app.routes}

    async def test_first_event_is_the_retry_directive(self, app):
        chunks = await _read_stream(app, stop_after=1)

        assert chunks[0] == "retry: 1000\n\n"

    async def test_each_app_streams_its_own_cache(self, price_cache, data_source):
        other_cache = PriceCache()
        other_cache.update("PYPL", 60.0)
        other_source = StubDataSource(other_cache)

        first = await _first_payload(_app(price_cache, data_source, enable_snapshot_task=False))
        second = await _first_payload(_app(other_cache, other_source, enable_snapshot_task=False))

        assert set(first) == {"AAPL", "MSFT", "NVDA"}
        assert set(second) == {"PYPL"}
        assert first["AAPL"]["price"] == 195.0
        assert second["PYPL"]["price"] == 60.0


def _stream_endpoint(app):
    """The SSE route's handler as the app actually has it registered.

    Going through the app's own route object is what makes this a test of
    `_scoped_stream_router`: `create_stream_router` appends to a module-level
    router, so a stale route would still be bound to a previous app's cache.
    """
    routes = [route for route in app.routes if getattr(route, "path", None) == "/api/stream/prices"]
    assert len(routes) == 1, f"expected exactly one stream route, got {len(routes)}"
    return routes[0].endpoint


async def _read_stream(app, stop_after: int = 2) -> list[str]:
    """Drive the SSE generator directly and close it after `stop_after` chunks.

    A `TestClient` stream cannot be used here: Starlette's test transport never
    delivers `http.disconnect`, so `_generate_events` (frozen, and correct under
    real uvicorn) would loop forever. Closing the body iterator raises
    `GeneratorExit` at its `yield`, which ends it immediately and deterministically.
    """
    response = await _stream_endpoint(app)(_connected_request())

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"

    chunks: list[str] = []
    body = response.body_iterator
    try:
        async for chunk in body:
            chunks.append(chunk)
            if len(chunks) >= stop_after:
                break
    finally:
        await body.aclose()
    return chunks


async def _first_payload(app) -> dict:
    """The decoded JSON of the stream's first `data:` event."""
    for chunk in await _read_stream(app):
        if chunk.startswith("data: "):
            return json.loads(chunk[len("data: ") :])
    raise AssertionError("no data event received")


def _connected_request() -> Request:
    """A still-connected client: `receive` never yields `http.disconnect`."""

    async def receive() -> dict:
        return {"type": "http.request"}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/api/stream/prices",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
        },
        receive,
    )
