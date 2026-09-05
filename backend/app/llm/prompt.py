"""System prompt and message construction (CONTRACTS.md section 5.4)."""

from collections.abc import Sequence
from typing import Any

# How many of the most recent chat rows are replayed to the model.
HISTORY_TURNS = 10

PERSONA = (
    "You are FinAlly, an AI trading assistant embedded in a simulated trading "
    "workstation. The portfolio is virtual money -- there is no real risk -- but you "
    "behave like a professional desk analyst."
)

RULES = """RULES
- Be concise and data-driven. Lead with numbers, not pleasantries. A few short sentences.
- Use ONLY the prices shown above. Never invent, estimate or recall a price from memory.
- You may only trade or add tickers that have a live price above. If the user names a
  ticker with no live price, say so instead of guessing.
- Execute trades when the user asks for them or agrees to a suggestion: put them in the
  `trades` array. Do not ask for confirmation -- fills are instant market orders.
- Only include a trade you actually intend to execute now; discussion alone means an
  empty `trades` array.
- Use `watchlist_changes` to add or remove tickers the user wants to track.
- Quantities are shares and may be fractional; they must be greater than zero.
- Always answer with JSON matching the schema: `message` (your reply to the user),
  `trades` (list of {ticker, side, quantity}), `watchlist_changes`
  (list of {ticker, action}). Use empty arrays when there is nothing to do."""


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _num(value: Any, places: int = 2) -> str:
    try:
        return f"{float(value):,.{places}f}"
    except (TypeError, ValueError):
        return "n/a"


def _qty(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _positions_block(portfolio: dict[str, Any]) -> str:
    positions = portfolio.get("positions") or []
    if not positions:
        return "POSITIONS\n- none (the portfolio is all cash)"
    lines = ["POSITIONS"]
    for position in positions:
        lines.append(
            "- {ticker}: qty {qty} | avg cost {avg} | price {price} | "
            "market value {value} | unrealized P&L {pnl} ({pnl_pct}%) | weight {weight}%".format(
                ticker=position.get("ticker", "?"),
                qty=_qty(position.get("quantity")),
                avg=_money(position.get("avg_cost")),
                price=_money(position.get("current_price")),
                value=_money(position.get("market_value")),
                pnl=_money(position.get("unrealized_pnl")),
                pnl_pct=_num(position.get("unrealized_pnl_percent")),
                weight=_num(position.get("weight")),
            )
        )
    return "\n".join(lines)


def _watchlist_block(watchlist: Sequence[dict[str, Any]]) -> str:
    if not watchlist:
        return "WATCHLIST (live prices)\n- empty"
    lines = ["WATCHLIST (live prices)"]
    for item in watchlist:
        ticker = item.get("ticker", "?")
        price = item.get("price")
        if price is None:
            lines.append(f"- {ticker}: no live price yet (not tradable)")
            continue
        change_percent = item.get("change_percent")
        change_text = "n/a" if change_percent is None else f"{_num(change_percent)}%"
        lines.append(f"- {ticker}: {_money(price)} (day {change_text})")
    return "\n".join(lines)


def build_system_prompt(
    portfolio: dict[str, Any], watchlist: Sequence[dict[str, Any]]
) -> str:
    """Persona + full live account context."""
    account = "\n".join(
        [
            "ACCOUNT",
            f"- cash available: {_money(portfolio.get('cash_balance'))}",
            f"- positions value: {_money(portfolio.get('positions_value'))}",
            f"- total portfolio value: {_money(portfolio.get('total_value'))}",
            f"- total cost basis: {_money(portfolio.get('total_cost_basis'))}",
            "- total unrealized P&L: "
            f"{_money(portfolio.get('total_unrealized_pnl'))} "
            f"({_num(portfolio.get('total_unrealized_pnl_percent'))}%)",
        ]
    )
    return "\n\n".join(
        [
            PERSONA,
            account,
            _positions_block(portfolio),
            _watchlist_block(watchlist),
            RULES,
        ]
    )


def build_messages(
    portfolio: dict[str, Any],
    watchlist: Sequence[dict[str, Any]],
    history: Sequence[Any],
    message: str,
) -> list[dict[str, str]]:
    """System prompt, then the last `HISTORY_TURNS` chat rows, then the new message."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(portfolio, watchlist)}
    ]
    for row in list(history)[-HISTORY_TURNS:]:
        role = getattr(row, "role", None)
        content = getattr(row, "content", None)
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages
