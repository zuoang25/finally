"""`GET /api/health` (CONTRACTS.md section 4.1)."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class TestHealth:
    def test_shape(self, client):
        body = client.get("/api/health").json()

        assert body == {
            "status": "ok",
            "market_data_source": "simulator",
            "llm_mock": True,
            "tickers_tracked": 10,
        }

    def test_reports_massive_when_a_key_is_configured(self, price_cache, data_source):
        app = create_app(
            settings=Settings(massive_api_key="abc123", llm_mock=False),
            price_cache=price_cache,
            market_data_source=data_source,
            enable_snapshot_task=False,
            static_dir=None,
        )
        with TestClient(app) as client:
            body = client.get("/api/health").json()

        assert body["market_data_source"] == "massive"
        assert body["llm_mock"] is False

    def test_source_started_on_the_persisted_watchlist(self, client, data_source):
        assert data_source.started_with[0] == "AAPL"
        assert len(data_source.started_with) == 10
