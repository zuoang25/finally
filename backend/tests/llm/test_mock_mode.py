"""Every row of the frozen mock behaviour table (CONTRACTS.md section 5.3)."""

import pytest

from app.llm import ChatService
from app.llm.mock import build_mock_response, find_quantity, find_ticker, known_tickers

from .conftest import FakeClient, FakePortfolioService, FakeWatchlistService


def make_service(portfolio_service, watchlist_service, **kwargs) -> ChatService:
    """Mock-mode service whose client explodes if it is ever called."""
    client = FakeClient(error=AssertionError("the provider must not be called in mock mode"))
    return ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=client,
        mock=True,
        **kwargs,
    )


async def test_buy_executes_trade(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("buy 5 AAPL")

    assert turn.message.startswith("Executed: bought ")
    assert turn.actions == [
        {
            "type": "trade",
            "status": "executed",
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 5.0,
            "price": 190.0,
            "detail": "Bought 5 AAPL @ $190.00",
        }
    ]
    assert portfolio_service.positions["AAPL"]["quantity"] == 5.0
    assert portfolio_service.cash == pytest.approx(10000.0 - 5 * 190.0)


async def test_sell_executes_trade(portfolio_service, watchlist_service):
    portfolio_service.positions["AAPL"] = {"quantity": 10.0, "avg_cost": 180.0}
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("sell 4 AAPL now")

    assert turn.message.startswith("Executed: sold ")
    action = turn.actions[0]
    assert action["type"] == "trade"
    assert action["status"] == "executed"
    assert action["side"] == "sell"
    assert action["quantity"] == 4.0
    assert action["price"] == 190.0
    assert portfolio_service.positions["AAPL"]["quantity"] == 6.0


async def test_add_watchlist_ticker(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("please add MSFT")

    assert turn.message.startswith("Added ")
    assert turn.actions == [
        {
            "type": "watchlist",
            "status": "executed",
            "ticker": "MSFT",
            "action": "add",
            "detail": "Added MSFT to watchlist",
        }
    ]
    assert "MSFT" in watchlist_service.tickers


async def test_remove_watchlist_ticker(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("remove TSLA from my list")

    assert turn.message.startswith("Removed ")
    assert turn.actions[0]["type"] == "watchlist"
    assert turn.actions[0]["action"] == "remove"
    assert turn.actions[0]["status"] == "executed"
    assert "TSLA" not in watchlist_service.tickers


async def test_fallback_reports_cash_and_position_count(portfolio_service, watchlist_service):
    portfolio_service.positions["NVDA"] = {"quantity": 2.0, "avg_cost": 700.0}
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("how am I doing?")

    assert turn.message.startswith("MOCK: ")
    assert "$10,000.00" in turn.message
    assert "1 position" in turn.message
    assert turn.actions == []


async def test_fallback_when_buy_has_no_quantity(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("should I buy AAPL")

    assert turn.message.startswith("MOCK: ")
    assert turn.actions == []


async def test_mock_buy_without_cash_still_reports_failed_action(
    watchlist_service,
):
    portfolio_service = FakePortfolioService(cash=100.0)
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("buy 1000 NVDA")

    assert turn.message.startswith("Executed: bought ")
    action = turn.actions[0]
    assert action["status"] == "failed"
    assert action["price"] is None
    assert action["quantity"] == 1000.0
    assert "Insufficient cash" in action["detail"]
    assert "Could not complete: Insufficient cash" in turn.message
    assert portfolio_service.positions == {}


async def test_mock_add_of_existing_ticker_fails(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("add AAPL")

    assert turn.message.startswith("Added ")
    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "AAPL is already on the watchlist"


async def test_mock_remove_of_absent_ticker_fails(portfolio_service, watchlist_service):
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("remove MSFT")

    assert turn.actions[0]["status"] == "failed"
    assert turn.actions[0]["detail"] == "MSFT is not on the watchlist"


async def test_mock_makes_no_provider_call(portfolio_service, watchlist_service):
    client = FakeClient(error=AssertionError("must not be called"))
    service = ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=client,
        mock=True,
    )
    await service.handle_message("hello there")
    assert client.calls == []


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "Yes"])
async def test_llm_mock_env_var_is_truthy(monkeypatch, portfolio_service, watchlist_service, value):
    monkeypatch.setenv("LLM_MOCK", value)
    service = ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=FakeClient(error=AssertionError("must not be called")),
    )
    assert service.mock_enabled is True
    turn = await service.handle_message("hello")
    assert turn.message.startswith("MOCK: ")


@pytest.mark.parametrize("value", ["false", "0", "no", ""])
def test_llm_mock_env_var_is_falsy(monkeypatch, portfolio_service, watchlist_service, value):
    monkeypatch.setenv("LLM_MOCK", value)
    service = ChatService(
        portfolio_service=portfolio_service,
        watchlist_service=watchlist_service,
        client=FakeClient(),
    )
    assert service.mock_enabled is False


def test_known_tickers_unions_watchlist_and_seed_prices():
    watchlist = [{"ticker": "PYPL"}, {"ticker": "AAPL"}]
    tickers = known_tickers(watchlist)
    assert "PYPL" in tickers  # from the watchlist
    assert "NFLX" in tickers  # from SEED_PRICES


def test_find_ticker_takes_the_first_known_standalone_token():
    tickers = {"AAPL", "MSFT"}
    assert find_ticker("sell aapl and msft", tickers) == "AAPL"
    assert find_ticker("no tickers here", tickers) is None
    assert find_ticker("AAPL5 is not standalone", tickers) is None


def test_find_quantity_takes_the_first_number():
    assert find_quantity("buy 12 AAPL then 3 MSFT") == 12.0
    assert find_quantity("buy 2.5 AAPL") == 2.5
    assert find_quantity("buy some AAPL") is None


def test_build_mock_response_is_deterministic():
    portfolio = FakePortfolioService().get_portfolio()
    watchlist: list[dict] = []
    first = build_mock_response("buy 3 AAPL", portfolio, watchlist)
    second = build_mock_response("buy 3 AAPL", portfolio, watchlist)
    assert first.model_dump() == second.model_dump()


async def test_mock_service_uses_live_watchlist_for_ticker_detection(portfolio_service):
    watchlist_service = FakeWatchlistService(tickers=["PYPL"])
    service = make_service(portfolio_service, watchlist_service)
    turn = await service.handle_message("buy 2 PYPL")

    assert turn.actions[0]["ticker"] == "PYPL"
    assert turn.actions[0]["status"] == "executed"
