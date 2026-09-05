"""LiteLLM -> OpenRouter -> Cerebras client (see the `cerebras-inference` skill).

`litellm` is imported lazily so that importing `app.llm` never fails and never
costs anything in `LLM_MOCK=true` mode (E2E, CI, no-API-key development).
"""

import asyncio
import os
from collections.abc import Callable
from typing import Any

from app.llm.schemas import AssistantResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY: dict[str, Any] = {"provider": {"order": ["cerebras"]}}
REASONING_EFFORT = "low"

_TRUTHY = {"true", "1", "yes"}


class LLMUnavailableError(Exception):
    """The provider could not be reached or refused the request.

    The API layer maps this to HTTP 503 ``AI assistant unavailable: <reason>``
    per CONTRACTS.md section 4.8.
    """


def is_mock_enabled() -> bool:
    """`LLM_MOCK` is truthy for "true"/"1"/"yes", case-insensitively."""
    return os.environ.get("LLM_MOCK", "").strip().lower() in _TRUTHY


def _load_completion() -> Callable[..., Any]:
    from litellm import completion

    return completion


class LLMClient:
    """Thin wrapper around a single blocking `litellm.completion` call."""

    def __init__(
        self,
        model: str = MODEL,
        extra_body: dict[str, Any] | None = None,
        reasoning_effort: str = REASONING_EFFORT,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model
        self.extra_body = EXTRA_BODY if extra_body is None else extra_body
        self.reasoning_effort = reasoning_effort
        self._completion_fn = completion_fn

    async def complete(self, messages: list[dict[str, str]]) -> str:
        """Run the blocking completion in a worker thread and return raw content."""
        return await asyncio.to_thread(self.complete_sync, messages)

    def complete_sync(self, messages: list[dict[str, str]]) -> str:
        completion = self._completion_fn or _load_completion()
        try:
            response = completion(
                model=self.model,
                messages=messages,
                response_format=AssistantResponse,
                reasoning_effort=self.reasoning_effort,
                extra_body=self.extra_body,
            )
        except Exception as exc:  # provider/network/auth failure -> 503 upstream
            raise LLMUnavailableError(str(exc) or exc.__class__.__name__) from exc

        try:
            content = response.choices[0].message.content
        except Exception as exc:
            raise LLMUnavailableError(f"malformed provider response: {exc}") from exc
        return content or ""
