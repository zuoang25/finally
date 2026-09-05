"""Portfolio endpoints (CONTRACTS.md sections 4.5-4.7)."""

import pytest

from app.db import list_snapshots, record_snapshot, set_cash_balance, upsert_position


class TestGetPortfolio:
    def test_empty(self, client):
        body = client.get("/api/portfolio").json()

        assert body == {
            "cash_balance": 10000.0,
            "positions": [],
            "positions_value": 0.0,
            "total_value": 10000.0,
            "total_cost_basis": 0.0,
            "total_unrealized_pnl": 0.0,
            "total_unrealized_pnl_percent": 0.0,
        }

    def test_position_carries_exactly_the_contract_keys(self, client):
        set_cash_balance(8050.0)
        upsert_position("AAPL", 10.0, 190.0)

        position = client.get("/api/portfolio").json()["positions"][0]

        assert position == {
            "ticker": "AAPL",
            "quantity": 10.0,
            "avg_cost": 190.0,
            "current_price": 195.0,
            "market_value": 1950.0,
            "cost_basis": 1900.0,
            "unrealized_pnl": 50.0,
            "unrealized_pnl_percent": pytest.approx(2.6316),
            # A percentage of total value (0-100), not a fraction.
            "weight": pytest.approx(1950.0 / 10000.0 * 100, abs=1e-3),
        }

    def test_with_positions(self, client):
        set_cash_balance(8050.0)
        upsert_position("AAPL", 10.0, 190.0)  # 195.00 -> 1950.00
        upsert_position("NVDA", 1.0, 900.0)  # 820.50 -> a loss

        body = client.get("/api/portfolio").json()
        positions = body["positions"]

        assert [p["ticker"] for p in positions] == ["AAPL", "NVDA"]
        assert positions[0]["unrealized_pnl"] == 50.0
        assert positions[0]["unrealized_pnl_percent"] == pytest.approx(2.6316)
        assert positions[1]["unrealized_pnl"] == -79.5
        assert body["positions_value"] == 2770.5
        assert body["total_value"] == 10820.5
        assert body["total_cost_basis"] == 2800.0
        assert body["total_unrealized_pnl"] == -29.5
        assert sum(p["weight"] for p in positions) == pytest.approx(
            2770.5 / 10820.5 * 100, abs=1e-3
        )


class TestTrade:
    def test_buy(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "aapl", "quantity": 10, "side": "buy"}
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"trade", "portfolio"}
        assert body["trade"]["ticker"] == "AAPL"
        assert body["trade"]["side"] == "buy"
        assert body["trade"]["quantity"] == 10.0
        assert body["trade"]["price"] == 195.0
        assert body["trade"]["id"]
        assert body["trade"]["executed_at"].endswith("Z")
        assert body["portfolio"]["cash_balance"] == 8050.0
        assert body["portfolio"]["positions"][0]["ticker"] == "AAPL"

    def test_buy_records_a_snapshot(self, client):
        client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
        )

        assert len(list_snapshots()) == 1

    def test_sell(self, client):
        client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"}
        )

        body = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "sell"}
        ).json()

        assert body["trade"]["side"] == "sell"
        assert body["portfolio"]["positions"] == []
        assert body["portfolio"]["cash_balance"] == 10000.0

    def test_fractional_quantity(self, client):
        body = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0.5, "side": "buy"}
        ).json()

        assert body["trade"]["quantity"] == 0.5
        assert body["portfolio"]["cash_balance"] == 9902.5

    def test_insufficient_cash(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1000, "side": "buy"}
        )

        assert response.status_code == 400
        assert "Insufficient" in response.json()["detail"]

    def test_insufficient_shares(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"}
        )

        assert response.status_code == 400
        assert "Insufficient" in response.json()["detail"]

    def test_no_price_available(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "TSLA", "quantity": 1, "side": "buy"}
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "No price available for TSLA"

    def test_unwatched_ticker_with_a_price_is_tradable(self, client, price_cache):
        price_cache.update("PYPL", 60.0)

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "PYPL", "quantity": 1, "side": "buy"}
        )

        assert response.status_code == 200

    @pytest.mark.parametrize("quantity", [0, -1])
    def test_non_positive_quantity(self, client, quantity):
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": quantity, "side": "buy"},
        )

        assert response.status_code == 400

    def test_invalid_ticker(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "123", "quantity": 1, "side": "buy"}
        )

        assert response.status_code == 400

    def test_invalid_side(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"}
        )

        assert response.status_code == 422


class TestHistory:
    def test_empty(self, client):
        assert client.get("/api/portfolio/history").json() == {"snapshots": []}

    def test_oldest_first(self, client):
        record_snapshot(10000.0)
        record_snapshot(10500.0)
        record_snapshot(9900.0)

        snapshots = client.get("/api/portfolio/history").json()["snapshots"]

        assert [s["total_value"] for s in snapshots] == [10000.0, 10500.0, 9900.0]
        assert set(snapshots[0]) == {"total_value", "recorded_at"}
        assert snapshots[0]["recorded_at"].endswith("Z")

    def test_limit(self, client):
        for value in (1.0, 2.0, 3.0):
            record_snapshot(value)

        snapshots = client.get("/api/portfolio/history?limit=2").json()["snapshots"]

        assert [s["total_value"] for s in snapshots] == [1.0, 2.0]

    def test_invalid_limit(self, client):
        assert client.get("/api/portfolio/history?limit=0").status_code == 422
