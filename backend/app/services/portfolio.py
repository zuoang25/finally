"""Portfolio valuation and trade execution (CONTRACTS.md sections 4.5-4.7).

Every method here is synchronous: FastAPI runs the `def` route handlers that
call them in a threadpool, and the LLM `ChatService` calls them through
`PortfolioServiceProtocol` (CONTRACTS.md section 5.1).
"""

from __future__ import annotations

from typing import Any

from app.db import apply_trade, get_cash_balance, list_positions, record_snapshot
from app.market import PriceCache
from app.services.common import (
    NoPriceError,
    TradeValidationError,
    normalize_ticker,
    round_money,
    round_percent,
    round_quantity,
)

DEFAULT_USER_ID = "default"
SIDES = ("buy", "sell")


class PortfolioService:
    """Builds the portfolio payload and executes market orders."""

    def __init__(self, price_cache: PriceCache) -> None:
        self._cache = price_cache

    # -- valuation ---------------------------------------------------------

    def get_portfolio(self, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        """The section 4.5 payload: cash, positions with P&L, and totals."""
        cash_balance = get_cash_balance(user_id=user_id)
        rows = list_positions(user_id=user_id)

        valued: list[dict[str, Any]] = []
        positions_value = 0.0
        total_cost_basis = 0.0

        for row in rows:
            # Fall back to the average cost when the cache has no price yet, so
            # a held position never disappears from the valuation.
            current_price = self._cache.get_price(row.ticker)
            if current_price is None:
                current_price = row.avg_cost
            market_value = row.quantity * current_price
            cost_basis = row.quantity * row.avg_cost
            positions_value += market_value
            total_cost_basis += cost_basis
            valued.append(
                {
                    "ticker": row.ticker,
                    "quantity": row.quantity,
                    "avg_cost": row.avg_cost,
                    "current_price": current_price,
                    "market_value": market_value,
                    "cost_basis": cost_basis,
                }
            )

        total_value = cash_balance + positions_value
        total_unrealized_pnl = positions_value - total_cost_basis

        valued.sort(key=lambda item: item["market_value"], reverse=True)

        positions = [
            {
                "ticker": item["ticker"],
                "quantity": round_quantity(item["quantity"]),
                "avg_cost": round_money(item["avg_cost"]),
                "current_price": round_money(item["current_price"]),
                "market_value": round_money(item["market_value"]),
                "cost_basis": round_money(item["cost_basis"]),
                "unrealized_pnl": round_money(item["market_value"] - item["cost_basis"]),
                "unrealized_pnl_percent": round_percent(
                    (item["market_value"] - item["cost_basis"]) / item["cost_basis"] * 100
                    if item["cost_basis"]
                    else 0.0
                ),
                "weight": round_percent(
                    item["market_value"] / total_value * 100 if total_value else 0.0
                ),
            }
            for item in valued
        ]

        return {
            "cash_balance": round_money(cash_balance),
            "positions": positions,
            "positions_value": round_money(positions_value),
            "total_value": round_money(total_value),
            "total_cost_basis": round_money(total_cost_basis),
            "total_unrealized_pnl": round_money(total_unrealized_pnl),
            "total_unrealized_pnl_percent": round_percent(
                total_unrealized_pnl / total_cost_basis * 100 if total_cost_basis else 0.0
            ),
        }

    def total_value(self, user_id: str = DEFAULT_USER_ID) -> float:
        """Unrounded cash + market value of every position."""
        total = get_cash_balance(user_id=user_id)
        for row in list_positions(user_id=user_id):
            price = self._cache.get_price(row.ticker)
            total += row.quantity * (row.avg_cost if price is None else price)
        return total

    def record_snapshot(self, user_id: str = DEFAULT_USER_ID) -> float:
        """Append a `portfolio_snapshots` row for the current total value."""
        total = self.total_value(user_id=user_id)
        record_snapshot(total, user_id=user_id)
        return total

    # -- trading -----------------------------------------------------------

    def execute_trade(
        self,
        ticker: str,
        side: str,
        quantity: float,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        """Fill a market order at the cached price and snapshot the portfolio.

        Raises `InvalidTickerError` / `TradeValidationError` for a bad request,
        `NoPriceError` when the ticker has no live price, and the `app.db`
        `InsufficientFundsError` / `InsufficientSharesError` on a rejected fill.
        """
        symbol = normalize_ticker(ticker)
        if side not in SIDES:
            raise TradeValidationError('side must be "buy" or "sell"')
        try:
            qty = float(quantity)
        except (TypeError, ValueError) as exc:
            raise TradeValidationError("quantity must be a number") from exc
        if not qty > 0:
            raise TradeValidationError("quantity must be > 0")

        price = self._cache.get_price(symbol)
        if price is None:
            raise NoPriceError(f"No price available for {symbol}")

        trade = apply_trade(symbol, side, qty, price, user_id=user_id)
        # Snapshot immediately so the P&L chart shows the step change.
        self.record_snapshot(user_id=user_id)

        return {
            "id": trade.id,
            "ticker": trade.ticker,
            "side": trade.side,
            "quantity": round_quantity(trade.quantity),
            "price": round_money(trade.price),
            "executed_at": trade.executed_at,
        }
