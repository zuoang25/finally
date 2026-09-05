"""`ChatService` end to end against fake services -- no network, no API key."""

import json

import pytest

from app.db import list_chat_messages
from app.llm import ChatService, ChatTurn, LLMUnavailableError

from .conftest import FakeClient, FakePortfolioService, FakeWatchlistService


def make_service(portfolio_service, watchlist_service, content="", error=None) -> ChatService:
    return ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=FakeClient(content=content, error=error),
        mock=False,
    )


def response_json(message="ok", trades=None, watchlist_changes=None) -> str:
    return json.dumps(
        {
            "message": message,
            "trades": trades or [],
            "watchlist_changes": watchlist_changes or [],
        }
    )


# -- happy path -------------------------------------------------------------


async def test_executes_trades_and_watchlist_changes(portfolio_service, watchlist_service):
    content = response_json(
        message="Bought NVDA and added MSFT.",
        trades=[{"ticker": "nvda", "side": "buy", "quantity": 2}],
        watchlist_changes=[{"ticker": "msft", "action": "add"}],
    )
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy me some nvidia and watch microsoft")

    assert isinstance(turn, ChatTurn)
    assert turn.message == "Bought NVDA and added MSFT."
    assert turn.created_at
    assert turn.actions == [
        {
            "type": "trade",
            "status": "executed",
            "ticker": "NVDA",
            "side": "buy",
            "quantity": 2.0,
            "price": 800.0,
            "detail": "Bought 2 NVDA @ $800.00",
        },
        {
            "type": "watchlist",
            "status": "executed",
            "ticker": "MSFT",
            "action": "add",
            "detail": "Added MSFT to watchlist",
        },
    ]
    assert portfolio_service.trade_calls == [("NVDA", "buy", 2.0, "default")]
    assert "MSFT" in watchlist_service.tickers


async def test_no_actions_yields_an_empty_list(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, content=response_json("Hello."))
    turn = await service.handle_message("hi")

    assert turn.actions == []
    assert turn.message == "Hello."


async def test_watchlist_removal(portfolio_service, watchlist_service):
    content = response_json(
        message="Dropped TSLA.", watchlist_changes=[{"ticker": "TSLA", "action": "remove"}]
    )
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("stop tracking tesla")

    assert turn.actions[0]["status"] == "executed"
    assert turn.actions[0]["detail"] == "Removed TSLA from watchlist"
    assert "TSLA" not in watchlist_service.tickers


async def test_fractional_quantities_are_supported(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "AAPL", "side": "buy", "quantity": 2.5}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy a bit of apple")

    assert turn.actions[0]["quantity"] == 2.5
    assert turn.actions[0]["detail"] == "Bought 2.5 AAPL @ $190.00"


async def test_context_is_sent_to_the_provider(portfolio_service, watchlist_service):
    client = FakeClient(content=response_json("hi"))
    service = ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=client,
        mock=False,
    )
    await service.handle_message("first question")
    await service.handle_message("second question")

    system_prompt = client.calls[1][0]["content"]
    assert "FinAlly" in system_prompt
    assert "$10,000.00" in system_prompt
    # The second call replays the first turn.
    replayed = [m["content"] for m in client.calls[1][1:]]
    assert "first question" in replayed
    assert replayed[-1] == "second question"


# -- failed actions ---------------------------------------------------------


async def test_insufficient_funds_becomes_a_failed_action(watchlist_service):
    portfolio_service = FakePortfolioService(cash=100.0)
    content = response_json(
        message="Buying NVDA.", trades=[{"ticker": "NVDA", "side": "buy", "quantity": 10}]
    )
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("go big on nvidia")

    action = turn.actions[0]
    assert action["status"] == "failed"
    assert action["price"] is None
    assert action["ticker"] == "NVDA"
    assert action["side"] == "buy"
    assert action["quantity"] == 10.0
    assert "Insufficient cash" in action["detail"]
    assert "Could not complete" in turn.message


async def test_insufficient_shares_becomes_a_failed_action(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "AAPL", "side": "sell", "quantity": 3}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("sell my apple")

    assert turn.actions[0]["status"] == "failed"
    assert "Insufficient shares of AAPL" in turn.actions[0]["detail"]


async def test_unknown_ticker_becomes_a_failed_action(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "ZZZZ", "side": "buy", "quantity": 1}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy zzzz")

    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "No price available for ZZZZ"


async def test_duplicate_watchlist_add_becomes_a_failed_action(
    portfolio_service, watchlist_service
):
    content = response_json(watchlist_changes=[{"ticker": "AAPL", "action": "add"}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("watch apple")

    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "AAPL is already on the watchlist"


async def test_removing_an_absent_ticker_becomes_a_failed_action(
    portfolio_service, watchlist_service
):
    content = response_json(watchlist_changes=[{"ticker": "PYPL", "action": "remove"}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("drop paypal")

    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "PYPL is not on the watchlist"


async def test_invalid_watchlist_symbol_becomes_a_failed_action(
    portfolio_service, watchlist_service
):
    content = response_json(watchlist_changes=[{"ticker": "123", "action": "add"}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("watch 123")

    assert turn.actions[0]["status"] == "failed"
    assert "Invalid ticker" in turn.actions[0]["detail"]


async def test_non_positive_quantity_becomes_a_failed_action(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "AAPL", "side": "buy", "quantity": 0}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy nothing")

    assert turn.actions[0]["status"] == "failed"
    assert "greater than zero" in turn.actions[0]["detail"]
    assert portfolio_service.trade_calls == []


async def test_blank_ticker_becomes_a_failed_action(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "  ", "side": "buy", "quantity": 1}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy something")

    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "No ticker was specified for the trade"


async def test_unexpected_service_error_becomes_a_failed_action(
    portfolio_service, watchlist_service
):
    def explode(*args, **kwargs):
        raise RuntimeError("database on fire")

    portfolio_service.execute_trade = explode
    content = response_json(trades=[{"ticker": "AAPL", "side": "buy", "quantity": 1}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy apple")

    assert turn.actions[0]["status"] == "failed"
    assert "database on fire" in turn.actions[0]["detail"]


async def test_one_failure_does_not_abort_the_other_actions(watchlist_service):
    portfolio_service = FakePortfolioService(cash=500.0)
    content = response_json(
        message="Two trades.",
        trades=[
            {"ticker": "NVDA", "side": "buy", "quantity": 10},
            {"ticker": "AAPL", "side": "buy", "quantity": 2},
        ],
    )
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy both")

    assert [a["status"] for a in turn.actions] == ["failed", "executed"]
    assert portfolio_service.positions["AAPL"]["quantity"] == 2.0


# -- degraded provider output ----------------------------------------------


async def test_malformed_json_does_not_raise(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, content='{"message": "oops"')
    turn = await service.handle_message("hello")

    assert turn.message
    assert turn.actions == []


async def test_missing_message_still_executes_trades(portfolio_service, watchlist_service):
    content = json.dumps({"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]})
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("buy one apple")

    assert turn.message
    assert turn.actions[0]["status"] == "executed"


async def test_prose_response_is_passed_through(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, content="You are up 2% today.")
    turn = await service.handle_message("how am I doing")

    assert turn.message == "You are up 2% today."


async def test_provider_failure_raises_llm_unavailable(portfolio_service, watchlist_service):
    service = make_service(
        portfolio_service, watchlist_service, error=LLMUnavailableError("connection refused")
    )
    with pytest.raises(LLMUnavailableError, match="connection refused"):
        await service.handle_message("hello")


async def test_unexpected_client_failure_is_wrapped(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, error=RuntimeError("boom"))
    with pytest.raises(LLMUnavailableError, match="boom"):
        await service.handle_message("hello")


async def test_provider_failure_persists_nothing(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, error=LLMUnavailableError("down"))
    with pytest.raises(LLMUnavailableError):
        await service.handle_message("hello")
    assert list_chat_messages() == []


# -- persistence and validation --------------------------------------------


async def test_both_chat_rows_are_persisted(portfolio_service, watchlist_service):
    content = response_json(
        message="Bought AAPL.", trades=[{"ticker": "AAPL", "side": "buy", "quantity": 1}]
    )
    service = make_service(portfolio_service, watchlist_service, content=content)
    turn = await service.handle_message("  buy one apple  ")

    rows = list_chat_messages()
    assert [row.role for row in rows] == ["user", "assistant"]
    assert rows[0].content == "buy one apple"  # trimmed
    assert rows[0].actions is None
    assert rows[1].content == turn.message
    assert rows[1].actions == turn.actions  # JSON round-trip
    assert rows[1].created_at == turn.created_at


async def test_history_is_scoped_per_user(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service, content=response_json("hi"))
    await service.handle_message("mine", user_id="alice")

    assert list_chat_messages(user_id="alice")
    assert list_chat_messages(user_id="default") == []


async def test_user_id_is_forwarded_to_the_services(portfolio_service, watchlist_service):
    content = response_json(trades=[{"ticker": "AAPL", "side": "buy", "quantity": 1}])
    service = make_service(portfolio_service, watchlist_service, content=content)
    await service.handle_message("buy apple", user_id="alice")

    assert portfolio_service.trade_calls == [("AAPL", "buy", 1.0, "alice")]


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
async def test_empty_message_is_rejected(portfolio_service, watchlist_service, message):
    service = make_service(portfolio_service, watchlist_service, content=response_json())
    with pytest.raises(ValueError, match="must not be empty"):
        await service.handle_message(message)
    assert list_chat_messages() == []


def test_service_accepts_only_the_two_injected_services():
    service = ChatService(
        portfolio_service=FakePortfolioService(),
        watchlist_service=FakeWatchlistService(),
    )
    assert service.client is not None
