"""Fixtures for the LLM test suite.

Everything here runs offline: no network, no `OPENROUTER_API_KEY`, and a
throwaway SQLite file per test. The fake services satisfy the protocols in
`app.llm.protocols` structurally and are backed by real in-memory state, so a
trade that runs out of cash genuinely fails.
"""

import re
import uuid

import pytest

from app.db import (
    DuplicateTickerError,
    InsufficientFundsError,
    InsufficientSharesError,
    utcnow_iso,
)
from app.db.connection import init_db
from app.llm.client import LLMUnavailableError

TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")

DEFAULT_PRICES = {
    "AAPL": 190.00,
    "NVDA": 800.00,
    "TSLA": 250.00,
    "MSFT": 420.00,
    "PYPL": 65.00,
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the db layer at a per-test SQLite file."""
    db_file = tmp_path / "test_llm.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))
    init_db()
    yield db_file


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Prove the suite never depends on a provider credential."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MOCK", raising=False)


class FakePortfolioService:
    """In-memory portfolio implementing `PortfolioServiceProtocol`."""

    def __init__(self, cash: float = 10000.0, prices: dict[str, float] | None = None):
        self.cash = cash
        self.prices = dict(DEFAULT_PRICES if prices is None else prices)
        self.positions: dict[str, dict[str, float]] = {}
        self.trade_calls: list[tuple[str, str, float, str]] = []

    # -- protocol ----------------------------------------------------------

    def get_portfolio(self, user_id: str = "default") -> dict:
        positions = []
        positions_value = 0.0
        cost_basis = 0.0
        for ticker, held in sorted(self.positions.items()):
            price = self.prices.get(ticker, held["avg_cost"])
            market_value = price * held["quantity"]
            basis = held["avg_cost"] * held["quantity"]
            positions_value += market_value
            cost_basis += basis
            positions.append(
                {
                    "ticker": ticker,
                    "quantity": held["quantity"],
                    "avg_cost": held["avg_cost"],
                    "current_price": price,
                    "market_value": round(market_value, 2),
                    "cost_basis": round(basis, 2),
                    "unrealized_pnl": round(market_value - basis, 2),
                    "unrealized_pnl_percent": round(
                        (market_value - basis) / basis * 100 if basis else 0.0, 4
                    ),
                    "weight": 0.0,
                }
            )
        total_value = self.cash + positions_value
        for position in positions:
            position["weight"] = round(
                position["market_value"] / total_value * 100 if total_value else 0.0, 4
            )
        return {
            "cash_balance": round(self.cash, 2),
            "positions": positions,
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "total_cost_basis": round(cost_basis, 2),
            "total_unrealized_pnl": round(positions_value - cost_basis, 2),
            "total_unrealized_pnl_percent": round(
                (positions_value - cost_basis) / cost_basis * 100 if cost_basis else 0.0, 4
            ),
        }

    def execute_trade(
        self, ticker: str, side: str, quantity: float, user_id: str = "default"
    ) -> dict:
        self.trade_calls.append((ticker, side, quantity, user_id))
        price = self.prices.get(ticker)
        if price is None:
            raise ValueError(f"No price available for {ticker}")
        if side == "buy":
            cost = price * quantity
            if cost > self.cash + 1e-9:
                raise InsufficientFundsError(cost, self.cash)
            held = self.positions.get(ticker, {"quantity": 0.0, "avg_cost": 0.0})
            new_qty = held["quantity"] + quantity
            self.positions[ticker] = {
                "quantity": new_qty,
                "avg_cost": round(
                    (held["quantity"] * held["avg_cost"] + quantity * price) / new_qty, 6
                ),
            }
            self.cash -= cost
        else:
            held = self.positions.get(ticker)
            have = held["quantity"] if held else 0.0
            if quantity > have + 1e-9:
                raise InsufficientSharesError(ticker, quantity, have)
            remaining = have - quantity
            if remaining <= 1e-9:
                self.positions.pop(ticker, None)
            else:
                self.positions[ticker] = {
                    "quantity": remaining,
                    "avg_cost": held["avg_cost"],
                }
            self.cash += price * quantity
        return {
            "id": uuid.uuid4().hex,
            "ticker": ticker,
            "side": side,
            "quantity": float(quantity),
            "price": price,
            "executed_at": utcnow_iso(),
        }


class FakeWatchlistService:
    """In-memory watchlist implementing `WatchlistServiceProtocol`."""

    def __init__(self, tickers: list[str] | None = None, prices: dict[str, float] | None = None):
        self.tickers = list(["AAPL", "NVDA", "TSLA"] if tickers is None else tickers)
        self.prices = dict(DEFAULT_PRICES if prices is None else prices)

    async def get_watchlist(self, user_id: str = "default") -> list[dict]:
        return [
            {
                "ticker": ticker,
                "price": self.prices.get(ticker),
                "previous_price": self.prices.get(ticker),
                "open_price": self.prices.get(ticker),
                "change": 0.0,
                "change_percent": 0.0,
                "direction": "flat",
                "added_at": utcnow_iso(),
            }
            for ticker in self.tickers
        ]

    async def add_ticker(self, ticker: str, user_id: str = "default") -> dict:
        if not TICKER_RE.match(ticker):
            raise ValueError(f"Invalid ticker: {ticker}")
        if ticker in self.tickers:
            raise DuplicateTickerError(ticker)
        self.tickers.append(ticker)
        return {"ticker": ticker, "price": self.prices.get(ticker)}

    async def remove_ticker(self, ticker: str, user_id: str = "default") -> bool:
        if ticker not in self.tickers:
            return False
        self.tickers.remove(ticker)
        return True


class FakeClient:
    """Stands in for `LLMClient`: returns canned content or raises."""

    def __init__(self, content: str = "", error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.content


@pytest.fixture
def portfolio_service() -> FakePortfolioService:
    return FakePortfolioService()


@pytest.fixture
def watchlist_service() -> FakeWatchlistService:
    return FakeWatchlistService()


@pytest.fixture
def unavailable_client() -> FakeClient:
    return FakeClient(error=LLMUnavailableError("connection refused"))
