"""Chat endpoints (CONTRACTS.md sections 4.8-4.9).

The route is a thin serialiser over `app.llm.ChatService`; all LLM logic,
action execution and persistence live in that module.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status
from fastapi.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool

from app.api.deps import DEFAULT_USER_ID, ChatServiceDep
from app.api.schemas import ChatRequest
from app.db import list_chat_messages

router = APIRouter(prefix="/api/chat", tags=["chat"])

# `list_chat_messages(limit)` returns the OLDEST `limit` rows, but section 4.9
# wants the most RECENT `limit` rendered oldest-first. Widen the window until it
# stops coming back full, then keep the tail.
HISTORY_WINDOW = 1000
MAX_HISTORY_WINDOW = 64_000


def _recent_chat_messages(limit: int, user_id: str) -> list[Any]:
    """The most recent `limit` chat rows, still ordered oldest first."""
    window = max(HISTORY_WINDOW, limit)
    while True:
        rows = list_chat_messages(limit=window, user_id=user_id)
        if len(rows) < window or window >= MAX_HISTORY_WINDOW:
            return rows[-limit:]
        window *= 2


@router.post("")
async def chat(body: ChatRequest, service: ChatServiceDep) -> dict[str, Any]:
    """Send a message and get the assistant's reply plus executed actions."""
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Message must not be empty"
        )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI assistant unavailable: chat service is not configured",
        )

    try:
        turn = await service.handle_message(message, user_id=DEFAULT_USER_ID)
    except HTTPException:
        raise
    except ValueError as exc:
        # A rejected request, not a provider outage (e.g. an empty message).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - any provider failure surfaces as 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI assistant unavailable: {exc}",
        ) from exc

    return {
        "message": turn.message,
        "actions": list(turn.actions or []),
        "created_at": turn.created_at,
    }


@router.get("/history")
async def get_history(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """The most recent `limit` turns, rendered oldest first."""
    rows = await run_in_threadpool(_recent_chat_messages, limit, DEFAULT_USER_ID)
    return {
        "messages": [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "actions": row.actions,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
