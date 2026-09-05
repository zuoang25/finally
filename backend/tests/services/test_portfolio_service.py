"""Unit tests for `PortfolioService` (CONTRACTS.md sections 4.5-4.6)."""

import pytest

from app.db import (
    InsufficientFundsError,
    InsufficientSharesError,
    apply_trade,
    get_cash_balance,
    list_snapshots,
    set_cash_balance,
    upsert_position,
)
from app.services.common import InvalidTickerError, NoPriceError, TradeValidationError


class TestGetPortfolio:
    def test_no_positions(self, portfolio_service):
        payload = portfolio_service.get_portfolio()

        assert payload["cash_balance"] == 10000.0
        assert payload["positions"] == []
        assert payload["positions_value"] == 0.0
        assert payload["total_value"] == payload["cash_balance"]
        assert payload["total_cost_basis"] == 0.0
        assert payload["total_unrealized_pnl"] == 0.0
        assert payload["total_unrealized_pnl_percent"] == 0.0

    def test_position_valuation_and_pnl(self, portfolio_service):
        upsert_position("AAPL", 10.0, 190.00)
        set_cash_balance(8100.0)

        payload = portfolio_service.get_portfolio()
        position = payload["positions"][0]

        assert position["ticker"] == "AAPL"
        assert position["quantity"] == 10.0
        assert position["avg_cost"] == 190.0
        assert position["current_price"] == 195.0
        assert position["market_value"] == 1950.0
        assert position["cost_basis"] == 1900.0
        assert position["unrealized_pnl"] == 50.0
        assert position["unrealized_pnl_percent"] == pytest.approx(2.6316)
        # weight is a percentage of total value (8100 + 1950 = 10050)
        assert position["weight"] == pytest.approx(19.403, abs=1e-3)
        assert payload["total_value"] == 10050.0
        assert payload["total_unrealized_pnl_percent"] == pytest.approx(2.6316)

    def test_sorted_by_market_value_descending(self, portfolio_service):
        upsert_position("AAPL", 1.0, 190.0)  # 195.00
        upsert_position("MSFT", 2.0, 420.0)  # 800.00
        upsert_position("NVDA", 1.0, 800.0)  # 820.50

        tickers = [p["ticker"] for p in portfolio_service.get_portfolio()["positions"]]

        assert tickers == ["NVDA", "MSFT", "AAPL"]

    def test_current_price_falls_back_to_avg_cost(self, portfolio_service):
        upsert_position("PYPL", 4.0, 60.0)

        position = portfolio_service.get_portfolio()["positions"][0]

        assert position["current_price"] == 60.0
        assert position["market_value"] == 240.0
        assert position["unrealized_pnl"] == 0.0

    def test_zero_cost_basis_yields_zero_percent(self, portfolio_service):
        upsert_position("AAPL", 5.0, 0.0)

        payload = portfolio_service.get_portfolio()

        assert payload["positions"][0]["unrealized_pnl_percent"] == 0.0
        assert payload["total_unrealized_pnl_percent"] == 0.0

    def test_rounding(self, portfolio_service):
        upsert_position("AAPL", 1.0 / 3.0, 1.0 / 7.0)

        position = portfolio_service.get_portfolio()["positions"][0]

        assert position["quantity"] == 0.333333
        assert position["avg_cost"] == 0.14
        assert isinstance(position["unrealized_pnl_percent"], float)
        assert round(position["unrealized_pnl_percent"], 4) == position["unrealized_pnl_percent"]


class TestExecuteTrade:
    def test_buy(self, portfolio_service):
        trade = portfolio_service.execute_trade("aapl", "buy", 10)

        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 10.0
        assert trade["price"] == 195.0
        assert trade["executed_at"].endswith("Z")
        assert set(trade) == {"id", "ticker", "side", "quantity", "price", "executed_at"}
        assert get_cash_balance() == pytest.approx(10000.0 - 1950.0)

    def test_buy_records_a_snapshot(self, portfolio_service):
        portfolio_service.execute_trade("AAPL", "buy", 1)

        snapshots = list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0].total_value == pytest.approx(10000.0)

    def test_sell(self, portfolio_service):
        apply_trade("AAPL", "buy", 10.0, 190.0)

        trade = portfolio_service.execute_trade("AAPL", "sell", 4)

        assert trade["side"] == "sell"
        assert trade["price"] == 195.0
        assert get_cash_balance() == pytest.approx(10000.0 - 1900.0 + 780.0)

    def test_insufficient_funds(self, portfolio_service):
        with pytest.raises(InsufficientFundsError):
            portfolio_service.execute_trade("AAPL", "buy", 1000)

    def test_insufficient_shares(self, portfolio_service):
        with pytest.raises(InsufficientSharesError):
            portfolio_service.execute_trade("AAPL", "sell", 1)

    def test_no_price(self, portfolio_service):
        with pytest.raises(NoPriceError, match="No price available for PYPL"):
            portfolio_service.execute_trade("PYPL", "buy", 1)

    def test_no_price_is_a_value_error(self, portfolio_service):
        # CONTRACTS.md section 5.1 promises a ValueError to the LLM service.
        with pytest.raises(ValueError):
            portfolio_service.execute_trade("PYPL", "buy", 1)

    def test_invalid_ticker(self, portfolio_service):
        with pytest.raises(InvalidTickerError):
            portfolio_service.execute_trade("123", "buy", 1)

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_non_positive_quantity(self, portfolio_service, quantity):
        with pytest.raises(TradeValidationError):
            portfolio_service.execute_trade("AAPL", "buy", quantity)

    def test_invalid_side(self, portfolio_service):
        with pytest.raises(TradeValidationError):
            portfolio_service.execute_trade("AAPL", "hold", 1)

    def test_failed_trade_records_no_snapshot(self, portfolio_service):
        with pytest.raises(InsufficientFundsError):
            portfolio_service.execute_trade("AAPL", "buy", 1000)

        assert list_snapshots() == []


class TestSnapshots:
    def test_total_value_is_unrounded_cash_plus_positions(self, portfolio_service):
        upsert_position("AAPL", 3.0, 100.0)

        assert portfolio_service.total_value() == pytest.approx(10000.0 + 585.0)

    def test_record_snapshot_persists(self, portfolio_service):
        total = portfolio_service.record_snapshot()

        rows = list_snapshots()

        assert len(rows) == 1
        assert rows[0].total_value == pytest.approx(total)
