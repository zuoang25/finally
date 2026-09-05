"""`ChatService` -- the whole `/api/chat` pipeline (CONTRACTS.md section 5).

build context -> call the LLM (or the deterministic mock) -> parse structured
output -> auto-execute every trade and watchlist change through the injected
services -> persist the user and assistant rows -> return a `ChatTurn` whose
`actions` are already in the section 4.8 wire shape.
"""

import asyncio
import math
from collections.abc import Sequence
from typing import Any

from app.db import DbError, add_chat_message, list_chat_messages, utcnow_iso
from app.llm.client import LLMClient, LLMUnavailableError, is_mock_enabled
from app.llm.mock import build_mock_response
from app.llm.prompt import HISTORY_TURNS, build_messages
from app.llm.protocols import PortfolioServiceProtocol, WatchlistServiceProtocol
from app.llm.schemas import (
    AssistantResponse,
    ChatTurn,
    Trade,
    WatchlistChange,
    parse_assistant_response,
)

DEFAULT_USER_ID = "default"

# `list_chat_messages` returns the OLDEST rows up to `limit`, so fetch a wide
# window and keep the tail to obtain the most recent turns.
_HISTORY_FETCH_LIMIT = 500


def _fmt_qty(quantity: float) -> str:
    text = f"{float(quantity):.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _trade_action(
    *,
    status: str,
    ticker: str,
    side: str,
    quantity: float,
    price: float | None,
    detail: str,
) -> dict[str, Any]:
    return {
        "type": "trade",
        "status": status,
        "ticker": ticker,
        "side": side,
        "quantity": float(quantity),
        "price": price,
        "detail": detail,
    }


def _watchlist_action(*, status: str, ticker: str, action: str, detail: str) -> dict[str, Any]:
    return {
        "type": "watchlist",
        "status": status,
        "ticker": ticker,
        "action": action,
        "detail": detail,
    }


class ChatService:
    """Owns the chat turn end to end. Constructed once in `main.py`."""

    def __init__(
        self,
        portfolio_service: PortfolioServiceProtocol,
        watchlist_service: WatchlistServiceProtocol,
        client: LLMClient | None = None,
        mock: bool | None = None,
    ) -> None:
        self.portfolio_service = portfolio_service
        self.watchlist_service = watchlist_service
        self.client = client or LLMClient()
        # `None` -> decide per request from the LLM_MOCK environment variable.
        self._mock = mock

    # -- public API ---------------------------------------------------------

    @property
    def mock_enabled(self) -> bool:
        return is_mock_enabled() if self._mock is None else self._mock

    async def handle_message(self, message: str, user_id: str = DEFAULT_USER_ID) -> ChatTurn:
        text = (message or "").strip()
        if not text:
            raise ValueError("Message must not be empty")

        portfolio = await asyncio.to_thread(self.portfolio_service.get_portfolio, user_id)
        watchlist = await self.watchlist_service.get_watchlist(user_id)

        response = await self._respond(text, portfolio, watchlist, user_id)
        actions = await self._execute_actions(response, user_id)
        final_message = _augment_message(response.message, actions)

        created_at = await self._persist(text, final_message, actions, user_id)
        return ChatTurn(message=final_message, actions=actions, created_at=created_at)

    # -- pipeline stages ----------------------------------------------------

    async def _respond(
        self,
        message: str,
        portfolio: dict[str, Any],
        watchlist: Sequence[dict[str, Any]],
        user_id: str,
    ) -> AssistantResponse:
        if self.mock_enabled:
            return build_mock_response(message, portfolio, watchlist)

        history = await self._history(user_id)
        messages = build_messages(portfolio, watchlist, history, message)
        try:
            raw = await self.client.complete(messages)
        except LLMUnavailableError:
            raise
        except Exception as exc:  # any unexpected client failure is still a 503
            raise LLMUnavailableError(str(exc) or exc.__class__.__name__) from exc
        return parse_assistant_response(raw)

    async def _history(self, user_id: str) -> list[Any]:
        try:
            rows = await asyncio.to_thread(list_chat_messages, _HISTORY_FETCH_LIMIT, user_id)
        except DbError:
            return []
        return rows[-HISTORY_TURNS:]

    async def _execute_actions(
        self, response: AssistantResponse, user_id: str
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for trade in response.trades:
            actions.append(await self._execute_trade(trade, user_id))
        for change in response.watchlist_changes:
            actions.append(await self._execute_watchlist_change(change, user_id))
        return actions

    async def _execute_trade(self, trade: Trade, user_id: str) -> dict[str, Any]:
        ticker = (trade.ticker or "").strip().upper()
        side = (trade.side or "").strip().lower()
        quantity = trade.quantity
        verb = "Bought" if side == "buy" else "Sold"

        if not ticker:
            return _trade_action(
                status="failed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=None,
                detail="No ticker was specified for the trade",
            )
        if side not in ("buy", "sell"):
            return _trade_action(
                status="failed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=None,
                detail=f"Unknown trade side: {trade.side}",
            )
        if not math.isfinite(quantity) or quantity <= 0:
            return _trade_action(
                status="failed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=None,
                detail=f"Quantity must be greater than zero (got {trade.quantity})",
            )

        try:
            result = await asyncio.to_thread(
                self.portfolio_service.execute_trade, ticker, side, quantity, user_id
            )
        except (DbError, ValueError) as exc:
            return _trade_action(
                status="failed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=None,
                detail=str(exc) or "Trade rejected",
            )
        except Exception as exc:
            return _trade_action(
                status="failed",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=None,
                detail=f"Trade failed: {exc}",
            )

        filled = result if isinstance(result, dict) else {}
        price = filled.get("price")
        filled_qty = filled.get("quantity", quantity)
        try:
            price = None if price is None else float(price)
        except (TypeError, ValueError):
            price = None
        try:
            filled_qty = float(filled_qty)
        except (TypeError, ValueError):
            filled_qty = quantity

        detail = f"{verb} {_fmt_qty(filled_qty)} {ticker}"
        if price is not None:
            detail += f" @ ${price:,.2f}"
        return _trade_action(
            status="executed",
            ticker=ticker,
            side=side,
            quantity=filled_qty,
            price=price,
            detail=detail,
        )

    async def _execute_watchlist_change(
        self, change: WatchlistChange, user_id: str
    ) -> dict[str, Any]:
        ticker = (change.ticker or "").strip().upper()
        action = (change.action or "").strip().lower()

        if not ticker:
            return _watchlist_action(
                status="failed",
                ticker=ticker,
                action=action,
                detail="No ticker was specified for the watchlist change",
            )
        if action not in ("add", "remove"):
            return _watchlist_action(
                status="failed",
                ticker=ticker,
                action=action,
                detail=f"Unknown watchlist action: {change.action}",
            )

        try:
            if action == "add":
                await self.watchlist_service.add_ticker(ticker, user_id)
                return _watchlist_action(
                    status="executed",
                    ticker=ticker,
                    action=action,
                    detail=f"Added {ticker} to watchlist",
                )
            removed = await self.watchlist_service.remove_ticker(ticker, user_id)
            if not removed:
                return _watchlist_action(
                    status="failed",
                    ticker=ticker,
                    action=action,
                    detail=f"{ticker} is not on the watchlist",
                )
            return _watchlist_action(
                status="executed",
                ticker=ticker,
                action=action,
                detail=f"Removed {ticker} from watchlist",
            )
        except (DbError, ValueError) as exc:
            return _watchlist_action(
                status="failed",
                ticker=ticker,
                action=action,
                detail=str(exc) or "Watchlist change rejected",
            )
        except Exception as exc:
            return _watchlist_action(
                status="failed",
                ticker=ticker,
                action=action,
                detail=f"Watchlist change failed: {exc}",
            )

    async def _persist(
        self,
        user_message: str,
        assistant_message: str,
        actions: list[dict[str, Any]],
        user_id: str,
    ) -> str:
        """Store both rows. A persistence failure must not lose the turn."""
        try:
            await asyncio.to_thread(add_chat_message, "user", user_message, None, user_id)
            row = await asyncio.to_thread(
                add_chat_message, "assistant", assistant_message, actions, user_id
            )
            return row.created_at
        except DbError:
            return utcnow_iso()


def _augment_message(message: str, actions: list[dict[str, Any]]) -> str:
    """Surface failed actions in the text, since the model executed blind."""
    failures = [a["detail"] for a in actions if a.get("status") == "failed" and a.get("detail")]
    if not failures:
        return message
    suffix = " ".join(f"Could not complete: {detail}." for detail in failures)
    return f"{message}\n\n{suffix}".strip()
