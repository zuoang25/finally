"""Watchlist endpoints (CONTRACTS.md sections 4.2-4.4)."""

import pytest

from app.db import apply_trade


class TestGetWatchlist:
    def test_returns_the_seeded_watchlist_in_added_order(self, client):
        body = client.get("/api/watchlist").json()

        assert [item["ticker"] for item in body["tickers"]] == [
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "NVDA",
            "META",
            "JPM",
            "V",
            "NFLX",
        ]

    def test_item_carries_live_and_day_change_fields(self, client):
        items = {i["ticker"]: i for i in client.get("/api/watchlist").json()["tickers"]}

        assert items["AAPL"] == {
            "ticker": "AAPL",
            "price": 195.0,
            "previous_price": 190.42,
            "open_price": 190.0,
            "change": 5.0,
            "change_percent": pytest.approx(2.6316),
            "direction": "up",
            "added_at": items["AAPL"]["added_at"],
        }

    def test_ticker_without_a_price_yet(self, client):
        items = {i["ticker"]: i for i in client.get("/api/watchlist").json()["tickers"]}

        assert items["TSLA"]["price"] is None
        assert items["TSLA"]["change"] is None
        assert items["TSLA"]["change_percent"] is None
        assert items["TSLA"]["open_price"] is None
        assert items["TSLA"]["direction"] == "flat"


class TestAddTicker:
    def test_created(self, client, data_source):
        response = client.post("/api/watchlist", json={"ticker": "pypl"})

        assert response.status_code == 201
        assert response.json()["ticker"] == "PYPL"
        assert response.json()["price"] is None
        assert data_source.added == ["PYPL"]
        assert "PYPL" in [i["ticker"] for i in client.get("/api/watchlist").json()["tickers"]]

    def test_created_with_a_live_price(self, client, price_cache):
        price_cache.update("PYPL", 60.0)
        price_cache.update("PYPL", 62.5)

        body = client.post("/api/watchlist", json={"ticker": "PYPL"}).json()

        assert body["price"] == 62.5
        assert body["previous_price"] == 60.0
        assert body["direction"] == "up"
        # An unseeded ticker opens at the price it was first observed at, so it
        # starts the session flat.
        assert body["open_price"] == 62.5
        assert body["change"] == 0.0

        price_cache.update("PYPL", 65.0)
        items = {i["ticker"]: i for i in client.get("/api/watchlist").json()["tickers"]}
        assert items["PYPL"]["open_price"] == 62.5
        assert items["PYPL"]["change"] == 2.5

    def test_duplicate_conflicts(self, client):
        response = client.post("/api/watchlist", json={"ticker": "AAPL"})

        assert response.status_code == 409
        assert "AAPL" in response.json()["detail"]

    @pytest.mark.parametrize("bad", ["", "123", "TOOLONGSYMBOL", "AA PL"])
    def test_invalid_symbol(self, client, bad):
        response = client.post("/api/watchlist", json={"ticker": bad})

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_missing_body_field(self, client):
        assert client.post("/api/watchlist", json={}).status_code == 422


class TestRemoveTicker:
    def test_no_content(self, client, data_source):
        response = client.delete("/api/watchlist/AAPL")

        assert response.status_code == 204
        assert response.content == b""
        assert data_source.removed == ["AAPL"]
        assert "AAPL" not in [i["ticker"] for i in client.get("/api/watchlist").json()["tickers"]]

    def test_lowercase_path_is_normalised(self, client):
        assert client.delete("/api/watchlist/aapl").status_code == 204

    def test_missing_ticker(self, client):
        response = client.delete("/api/watchlist/PYPL")

        assert response.status_code == 404
        assert "PYPL" in response.json()["detail"]

    def test_invalid_symbol(self, client):
        assert client.delete("/api/watchlist/123").status_code == 400

    def test_held_position_keeps_streaming(self, client, data_source):
        apply_trade("AAPL", "buy", 1.0, 195.0)

        assert client.delete("/api/watchlist/AAPL").status_code == 204
        assert data_source.removed == []
