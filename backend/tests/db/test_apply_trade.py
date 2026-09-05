"""Tests for the atomic apply_trade() transaction -- the trade maths from
CONTRACTS.md section 3.7 must hold exactly, and failures must roll back
cleanly (cash and positions unchanged).
"""

import pytest

from app.db import InsufficientFundsError, InsufficientSharesError
from app.db.repositories import (
    apply_trade,
    get_cash_balance,
    get_position,
    list_trades,
    set_cash_balance,
)


class TestApplyTradeBuy:
    def test_buy_creates_position_and_debits_cash(self, isolated_db):
        cash_before = get_cash_balance()
        trade = apply_trade("AAPL", "buy", 10.0, 190.0)

        assert trade.side == "buy"
        assert trade.ticker == "AAPL"
        assert trade.quantity == 10.0
        assert trade.price == 190.0

        position = get_position("AAPL")
        assert position is not None
        assert position.quantity == 10.0
        assert position.avg_cost == 190.0

        assert get_cash_balance() == pytest.approx(cash_before - 1900.0)

    def test_second_buy_recomputes_weighted_average_cost(self, isolated_db):
        apply_trade("AAPL", "buy", 10.0, 190.0)
        apply_trade("AAPL", "buy", 10.0, 210.0)

        position = get_position("AAPL")
        assert position.quantity == 20.0
        # (10*190 + 10*210) / 20 == 200.0
        assert position.avg_cost == pytest.approx(200.0)

    def test_buy_insufficient_funds_raises_and_rolls_back(self, isolated_db):
        cash_before = get_cash_balance()

        with pytest.raises(InsufficientFundsError):
            apply_trade("AAPL", "buy", 1000.0, 190.0)

        assert get_cash_balance() == cash_before
        assert get_position("AAPL") is None
        assert list_trades() == []

    def test_insufficient_funds_message_format(self, isolated_db):
        set_cash_balance(100.0)
        with pytest.raises(InsufficientFundsError) as excinfo:
            apply_trade("AAPL", "buy", 10.0, 195.0)
        assert str(excinfo.value) == "Insufficient cash: need $1950.00, have $100.00"

    def test_fractional_quantity_buy(self, isolated_db):
        trade = apply_trade("AAPL", "buy", 0.25, 190.0)
        assert trade.quantity == 0.25
        assert get_position("AAPL").quantity == 0.25

    def test_buy_at_exact_cash_balance_succeeds(self, isolated_db):
        cash = get_cash_balance()
        quantity = 10.0
        price = cash / quantity
        apply_trade("AAPL", "buy", quantity, price)
        assert get_cash_balance() == pytest.approx(0.0, abs=1e-6)


class TestApplyTradeSell:
    def test_sell_partial_reduces_quantity_and_keeps_avg_cost(self, isolated_db):
        apply_trade("AAPL", "buy", 10.0, 190.0)
        cash_after_buy = get_cash_balance()

        trade = apply_trade("AAPL", "sell", 4.0, 200.0)
        assert trade.side == "sell"

        position = get_position("AAPL")
        assert position is not None
        assert position.quantity == 6.0
        assert position.avg_cost == 190.0  # unchanged on sells

        assert get_cash_balance() == pytest.approx(cash_after_buy + 800.0)

    def test_sell_entire_position_deletes_row(self, isolated_db):
        apply_trade("AAPL", "buy", 10.0, 190.0)
        apply_trade("AAPL", "sell", 10.0, 200.0)
        assert get_position("AAPL") is None

    def test_sell_more_than_owned_raises_and_rolls_back(self, isolated_db):
        apply_trade("AAPL", "buy", 5.0, 190.0)
        cash_before = get_cash_balance()

        with pytest.raises(InsufficientSharesError):
            apply_trade("AAPL", "sell", 10.0, 200.0)

        assert get_cash_balance() == cash_before
        assert get_position("AAPL").quantity == 5.0

    def test_sell_with_no_position_raises(self, isolated_db):
        with pytest.raises(InsufficientSharesError):
            apply_trade("AAPL", "sell", 1.0, 190.0)

    def test_fractional_sell(self, isolated_db):
        apply_trade("AAPL", "buy", 1.0, 190.0)
        apply_trade("AAPL", "sell", 0.5, 200.0)
        assert get_position("AAPL").quantity == pytest.approx(0.5)

    def test_sell_exact_holding_succeeds_despite_fp_noise(self, isolated_db):
        apply_trade("AAPL", "buy", 0.1, 190.0)
        apply_trade("AAPL", "buy", 0.2, 190.0)
        # 0.1 + 0.2 != 0.3 exactly in binary floating point; the 1e-9
        # tolerance must absorb that when selling the full 0.3 position.
        apply_trade("AAPL", "sell", 0.3, 200.0)
        assert get_position("AAPL") is None


class TestApplyTradeGeneral:
    def test_records_trade_row(self, isolated_db):
        apply_trade("AAPL", "buy", 10.0, 190.0)
        trades = list_trades()
        assert len(trades) == 1
        assert trades[0].ticker == "AAPL"

    def test_invalid_side_raises_value_error(self, isolated_db):
        with pytest.raises(ValueError):
            apply_trade("AAPL", "hold", 1.0, 190.0)

    def test_zero_quantity_raises_value_error(self, isolated_db):
        with pytest.raises(ValueError):
            apply_trade("AAPL", "buy", 0.0, 190.0)

    def test_negative_quantity_raises_value_error(self, isolated_db):
        with pytest.raises(ValueError):
            apply_trade("AAPL", "buy", -1.0, 190.0)

    def test_apply_trade_is_scoped_per_user(self, isolated_db):
        default_cash_before = get_cash_balance()
        set_cash_balance(5000.0, user_id="alice")

        apply_trade("AAPL", "buy", 10.0, 190.0, user_id="alice")

        assert get_position("AAPL") is None
        alice_position = get_position("AAPL", user_id="alice")
        assert alice_position is not None
        assert alice_position.quantity == 10.0

        # The default user's cash and positions are untouched by alice's trade.
        assert get_cash_balance() == default_cash_before
        assert get_cash_balance(user_id="alice") == pytest.approx(5000.0 - 1900.0)
