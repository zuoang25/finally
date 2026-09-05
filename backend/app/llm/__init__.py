"""FinAlly LLM layer -- public surface.

The `/api/chat` route constructs `ChatService` once and awaits
`handle_message`; everything else here is internal detail exposed for tests.
See `planning/CONTRACTS.md` section 5.
"""

from app.llm.client import EXTRA_BODY, MODEL, LLMClient, LLMUnavailableError, is_mock_enabled
from app.llm.mock import build_mock_response
from app.llm.prompt import build_messages, build_system_prompt
from app.llm.protocols import PortfolioServiceProtocol, WatchlistServiceProtocol
from app.llm.schemas import (
    AssistantResponse,
    ChatTurn,
    Trade,
    WatchlistChange,
    parse_assistant_response,
)
from app.llm.service import ChatService

__all__ = [
    # service
    "ChatService",
    "ChatTurn",
    # schemas
    "AssistantResponse",
    "Trade",
    "WatchlistChange",
    "parse_assistant_response",
    # protocols
    "PortfolioServiceProtocol",
    "WatchlistServiceProtocol",
    # client
    "LLMClient",
    "LLMUnavailableError",
    "is_mock_enabled",
    "MODEL",
    "EXTRA_BODY",
    # prompt / mock helpers
    "build_system_prompt",
    "build_messages",
    "build_mock_response",
]
