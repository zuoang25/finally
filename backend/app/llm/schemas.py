"""Pydantic structured-output schemas and the chat result type.

See `planning/CONTRACTS.md` section 5.2 for the frozen shapes.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

# Message used when the provider returned something we could not make sense of.
UNPARSEABLE_MESSAGE = (
    "I could not read the assistant response properly, so I did not take any action. "
    "Please try rephrasing your request."
)
# Message used when the payload carried actions but no usable text.
MISSING_MESSAGE_TEXT = "Processing your request."

_MAX_SALVAGED_MESSAGE = 2000
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class Trade(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class AssistantResponse(BaseModel):
    message: str
    trades: list[Trade] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """What `/api/chat` serialises: CONTRACTS.md section 4.8."""

    message: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "actions": self.actions,
            "created_at": self.created_at,
        }


def _coerce_trades(raw: Any) -> list[Trade]:
    """Keep the trades that validate, drop the ones that do not."""
    if not isinstance(raw, list):
        return []
    trades: list[Trade] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            trades.append(Trade.model_validate(item))
        except Exception:
            continue
    return trades


def _coerce_watchlist_changes(raw: Any) -> list[WatchlistChange]:
    if not isinstance(raw, list):
        return []
    changes: list[WatchlistChange] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            changes.append(WatchlistChange.model_validate(item))
        except Exception:
            continue
    return changes


def _from_mapping(payload: dict[str, Any]) -> AssistantResponse:
    raw_message = payload.get("message")
    message = raw_message.strip() if isinstance(raw_message, str) else ""
    trades = _coerce_trades(payload.get("trades"))
    changes = _coerce_watchlist_changes(payload.get("watchlist_changes"))
    if not message:
        message = MISSING_MESSAGE_TEXT if (trades or changes) else UNPARSEABLE_MESSAGE
    return AssistantResponse(message=message, trades=trades, watchlist_changes=changes)


def parse_assistant_response(raw: str | None) -> AssistantResponse:
    """Best-effort parse of the model's structured output.

    Never raises: malformed JSON, a missing ``message`` or partially invalid
    action entries all degrade into a usable `AssistantResponse` so that a bad
    completion is reported to the user rather than turning into a 500.
    """
    text = (raw or "").strip()
    if not text:
        return AssistantResponse(message=UNPARSEABLE_MESSAGE)

    try:
        return AssistantResponse.model_validate_json(text)
    except Exception:
        pass

    for candidate in _json_candidates(text):
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return _from_mapping(payload)

    # Not JSON at all -- treat plain prose as the assistant's message.
    if not text.startswith("{") and not text.startswith("["):
        return AssistantResponse(message=text[:_MAX_SALVAGED_MESSAGE])
    return AssistantResponse(message=UNPARSEABLE_MESSAGE)


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    fenced = text
    if fenced.startswith("```"):
        fenced = re.sub(r"^```[a-zA-Z]*\n?", "", fenced)
        fenced = re.sub(r"\n?```$", "", fenced)
        candidates.append(fenced.strip())
    match = _JSON_OBJECT_RE.search(text)
    if match:
        candidates.append(match.group(0))
    return candidates
