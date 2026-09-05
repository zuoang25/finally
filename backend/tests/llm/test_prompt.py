"""System prompt content (CONTRACTS.md section 5.4)."""

from app.db import ChatRow
from app.llm.prompt import HISTORY_TURNS, build_messages, build_system_prompt

from .conftest import FakePortfolioService, FakeWatchlistService


def chat_row(role: str, content: str) -> ChatRow:
    return ChatRow(
        id="x",
        user_id="default",
        role=role,
        content=content,
        actions=None,
        created_at="2026-09-05T10:00:00Z",
    )


async def build_context():
    portfolio_service = FakePortfolioService(cash=8200.0)
    portfolio_service.positions["AAPL"] = {"quantity": 10.0, "avg_cost": 180.0}
    watchlist_service = FakeWatchlistService()
    return portfolio_service.get_portfolio(), await watchlist_service.get_watchlist()


async def test_system_prompt_contains_the_full_account_context():
    portfolio, watchlist = await build_context()
    prompt = build_system_prompt(portfolio, watchlist)

    assert "FinAlly, an AI trading assistant" in prompt
    assert "cash available: $8,200.00" in prompt
    assert "total portfolio value: $10,100.00" in prompt
    # Position detail: quantity, avg cost, current price and unrealized P&L.
    assert "AAPL: qty 10" in prompt
    assert "avg cost $180.00" in prompt
    assert "price $190.00" in prompt
    assert "unrealized P&L $100.00" in prompt
    # Watchlist with live prices.
    assert "NVDA: $800.00" in prompt


async def test_system_prompt_states_the_guardrails():
    portfolio, watchlist = await build_context()
    prompt = build_system_prompt(portfolio, watchlist)

    assert "Never invent" in prompt
    assert "live price" in prompt
    assert "concise" in prompt.lower()
    assert "watchlist_changes" in prompt


async def test_system_prompt_handles_an_empty_portfolio_and_missing_prices():
    portfolio = FakePortfolioService().get_portfolio()
    watchlist = [{"ticker": "PYPL", "price": None, "change_percent": None}]
    prompt = build_system_prompt(portfolio, watchlist)

    assert "none (the portfolio is all cash)" in prompt
    assert "PYPL: no live price yet" in prompt


async def test_build_messages_replays_the_last_ten_turns():
    portfolio, watchlist = await build_context()
    history = [chat_row("user" if i % 2 == 0 else "assistant", f"turn {i}") for i in range(14)]
    messages = build_messages(portfolio, watchlist, history, "what now?")

    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "what now?"}
    replayed = messages[1:-1]
    assert len(replayed) == HISTORY_TURNS
    assert replayed[0]["content"] == "turn 4"
    assert replayed[-1]["content"] == "turn 13"


async def test_build_messages_skips_rows_with_unusable_roles():
    portfolio, watchlist = await build_context()
    history = [chat_row("system", "ignored"), chat_row("user", "kept")]
    messages = build_messages(portfolio, watchlist, history, "hi")

    assert [m["content"] for m in messages[1:]] == ["kept", "hi"]


async def test_build_messages_with_no_history():
    portfolio, watchlist = await build_context()
    messages = build_messages(portfolio, watchlist, [], "hello")
    assert len(messages) == 2
