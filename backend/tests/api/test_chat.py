"""Chat endpoints (CONTRACTS.md sections 4.8-4.9).

`app.llm` is built independently, so these tests drive `/api/chat` through a
stub `ChatService` installed on `app.state` -- the route is only a serialiser.
"""

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import add_chat_message
from app.llm import LLMUnavailableError
from app.main import create_app


@dataclass
class StubTurn:
    message: str
    actions: list[dict] = field(default_factory=list)
    created_at: str = "2026-09-05T10:02:00Z"


class StubChatService:
    def __init__(self, turn: StubTurn | None = None, error: Exception | None = None) -> None:
        self.turn = turn
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def handle_message(self, message: str, user_id: str = "default") -> StubTurn:
        self.calls.append((message, user_id))
        if self.error is not None:
            raise self.error
        return self.turn


TRADE_ACTION = {
    "type": "trade",
    "status": "executed",
    "ticker": "NVDA",
    "side": "buy",
    "quantity": 5.0,
    "price": 820.5,
    "detail": "Bought 5 NVDA @ $820.50",
}


class TestChat:
    def test_serialises_the_turn(self, app, client):
        service = StubChatService(StubTurn("Bought 5 NVDA.", [TRADE_ACTION]))
        app.state.chat_service = service

        response = client.post("/api/chat", json={"message": "buy me 5 nvidia"})

        assert response.status_code == 200
        assert response.json() == {
            "message": "Bought 5 NVDA.",
            "actions": [TRADE_ACTION],
            "created_at": "2026-09-05T10:02:00Z",
        }
        assert service.calls == [("buy me 5 nvidia", "default")]

    def test_actions_default_to_an_empty_list(self, app, client):
        app.state.chat_service = StubChatService(StubTurn("Hello."))

        assert client.post("/api/chat", json={"message": "hi"}).json()["actions"] == []

    def test_message_is_trimmed_before_dispatch(self, app, client):
        service = StubChatService(StubTurn("Hello."))
        app.state.chat_service = service

        client.post("/api/chat", json={"message": "  hi  "})

        assert service.calls == [("hi", "default")]

    @pytest.mark.parametrize("message", ["", "   "])
    def test_empty_message(self, app, client, message):
        app.state.chat_service = StubChatService(StubTurn("Hello."))

        response = client.post("/api/chat", json={"message": message})

        assert response.status_code == 400

    def test_missing_field(self, client):
        assert client.post("/api/chat", json={}).status_code == 422

    def test_the_route_persists_nothing(self, app, client):
        """`ChatService` writes both chat rows itself -- the route must not double-write."""
        app.state.chat_service = StubChatService(StubTurn("Hello.", [TRADE_ACTION]))

        client.post("/api/chat", json={"message": "hi"})

        assert client.get("/api/chat/history").json()["messages"] == []

    def test_provider_failure(self, app, client):
        app.state.chat_service = StubChatService(error=RuntimeError("provider exploded"))

        response = client.post("/api/chat", json={"message": "hi"})

        assert response.status_code == 503
        assert response.json()["detail"] == "AI assistant unavailable: provider exploded"

    def test_llm_unavailable_error(self, app, client):
        app.state.chat_service = StubChatService(error=LLMUnavailableError("upstream 429"))

        response = client.post("/api/chat", json={"message": "hi"})

        assert response.status_code == 503
        assert response.json()["detail"] == "AI assistant unavailable: upstream 429"

    def test_value_error_is_a_bad_request(self, app, client):
        """A rejected message is the caller's fault, not a provider outage."""
        app.state.chat_service = StubChatService(error=ValueError("Message must not be empty"))

        response = client.post("/api/chat", json={"message": "hi"})

        assert response.status_code == 400
        assert response.json()["detail"] == "Message must not be empty"

    def test_service_unavailable(self, app, client):
        app.state.chat_service = None

        response = client.post("/api/chat", json={"message": "hi"})

        assert response.status_code == 503
        assert response.json()["detail"].startswith("AI assistant unavailable:")


class TestChatHistory:
    def test_empty(self, client):
        assert client.get("/api/chat/history").json() == {"messages": []}

    def test_oldest_first_with_actions(self, client):
        add_chat_message("user", "buy me 5 nvidia")
        add_chat_message("assistant", "Bought 5 NVDA.", actions=[TRADE_ACTION])

        messages = client.get("/api/chat/history").json()["messages"]

        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["actions"] is None
        assert messages[1]["actions"] == [TRADE_ACTION]
        assert set(messages[0]) == {"id", "role", "content", "actions", "created_at"}

    def test_limit_keeps_the_most_recent_turns_in_render_order(self, client):
        for index in range(5):
            add_chat_message("user", f"message {index}")

        messages = client.get("/api/chat/history?limit=2").json()["messages"]

        # `list_chat_messages` returns the OLDEST rows; section 4.9 wants the
        # newest ones, still oldest-first for rendering.
        assert [m["content"] for m in messages] == ["message 3", "message 4"]

    def test_limit_beyond_the_row_count_returns_everything(self, client):
        add_chat_message("user", "only one")

        messages = client.get("/api/chat/history?limit=50").json()["messages"]

        assert [m["content"] for m in messages] == ["only one"]

    def test_window_widens_past_the_first_page(self, client, monkeypatch):
        monkeypatch.setattr("app.api.chat.HISTORY_WINDOW", 4)
        for index in range(10):
            add_chat_message("user", f"message {index}")

        messages = client.get("/api/chat/history?limit=3").json()["messages"]

        assert [m["content"] for m in messages] == ["message 7", "message 8", "message 9"]

    @pytest.mark.parametrize("limit", [0, 501])
    def test_invalid_limit(self, client, limit):
        assert client.get(f"/api/chat/history?limit={limit}").status_code == 422


class TestRealChatServiceInMockMode:
    """The app's own `ChatService`, wired by `create_app`, never touching a provider.

    `create_app` passes `Settings.llm_mock` straight through to `ChatService`,
    so an injected `Settings(llm_mock=True)` guarantees the deterministic mock
    path regardless of what `.env` or the ambient environment holds.
    """

    def test_settings_decide_mock_mode(self, app, client, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)

        assert app.state.chat_service.mock_enabled is True

    def test_settings_can_also_disable_it(self, price_cache, data_source, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        other = create_app(
            settings=Settings(llm_mock=False),
            price_cache=price_cache,
            market_data_source=data_source,
            enable_snapshot_task=False,
            static_dir=None,
        )

        with TestClient(other):
            assert other.state.chat_service.mock_enabled is False

    def test_conversational_turn(self, client):
        body = client.post("/api/chat", json={"message": "how am I doing?"}).json()

        assert body["message"].startswith("MOCK: ")
        assert body["actions"] == []
        assert body["created_at"].endswith("Z")

    def test_executed_trade_round_trip(self, client):
        body = client.post("/api/chat", json={"message": "buy 2 AAPL"}).json()

        assert body["actions"] == [
            {
                "type": "trade",
                "status": "executed",
                "ticker": "AAPL",
                "side": "buy",
                "quantity": 2.0,
                "price": 195.0,
                "detail": body["actions"][0]["detail"],
            }
        ]
        assert client.get("/api/portfolio").json()["cash_balance"] == 9610.0

    def test_failed_trade_is_reported_not_raised(self, client):
        response = client.post("/api/chat", json={"message": "buy 1000 AAPL"})

        assert response.status_code == 200
        assert response.json()["actions"][0]["status"] == "failed"
        assert response.json()["actions"][0]["price"] is None

    def test_the_service_persists_both_rows_once(self, client):
        client.post("/api/chat", json={"message": "how am I doing?"})

        messages = client.get("/api/chat/history").json()["messages"]

        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "how am I doing?"
        assert messages[0]["actions"] is None
        assert messages[1]["actions"] == []
