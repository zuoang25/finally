"""Static file serving and the SPA fallback."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def static_dir(tmp_path):
    root = tmp_path / "static"
    (root / "_next").mkdir(parents=True)
    (root / "index.html").write_text("<html>finally</html>", encoding="utf-8")
    (root / "_next" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    (root / "portfolio").mkdir()
    (root / "portfolio" / "index.html").write_text("<html>portfolio</html>", encoding="utf-8")
    return root


def _client(price_cache, data_source, static_dir):
    app = create_app(
        settings=Settings(llm_mock=True),
        price_cache=price_cache,
        market_data_source=data_source,
        enable_snapshot_task=False,
        static_dir=static_dir,
    )
    return TestClient(app)


class TestWithoutStaticDir:
    def test_root_returns_a_json_placeholder(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["status"] == "ok"

    def test_unknown_api_path_is_a_json_404(self, client):
        response = client.get("/api/nope")

        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": "Not Found"}

    def test_bare_api_path_is_a_json_404(self, client):
        assert client.get("/api").status_code == 404


class TestWithStaticDir:
    def test_root_serves_index(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            response = client.get("/")

        assert response.status_code == 200
        assert response.text == "<html>finally</html>"

    def test_asset_is_served(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            response = client.get("/_next/app.js")

        assert response.status_code == 200
        assert "console.log" in response.text

    def test_nested_index(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            response = client.get("/portfolio/")

        assert response.text == "<html>portfolio</html>"

    def test_unknown_page_falls_back_to_index(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            response = client.get("/some/deep/route")

        assert response.status_code == 200
        assert response.text == "<html>finally</html>"

    def test_unknown_api_path_is_still_a_json_404(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            response = client.get("/api/nope")

        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

    def test_api_routes_still_win(self, price_cache, data_source, static_dir):
        with _client(price_cache, data_source, static_dir) as client:
            assert client.get("/api/health").json()["status"] == "ok"
