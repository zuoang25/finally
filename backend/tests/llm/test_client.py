"""LiteLLM client wiring -- verified without importing or calling litellm."""

from types import SimpleNamespace

import pytest

from app.llm.client import EXTRA_BODY, MODEL, LLMClient, LLMUnavailableError, is_mock_enabled
from app.llm.schemas import AssistantResponse


def fake_completion(content: str):
    calls: list[dict] = []

    def _completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    _completion.calls = calls
    return _completion


async def test_complete_sends_the_cerebras_parameters():
    completion = fake_completion('{"message":"ok"}')
    client = LLMClient(completion_fn=completion)

    result = await client.complete([{"role": "user", "content": "hi"}])

    assert result == '{"message":"ok"}'
    kwargs = completion.calls[0]
    assert kwargs["model"] == MODEL == "openrouter/openai/gpt-oss-120b"
    assert kwargs["extra_body"] == EXTRA_BODY == {"provider": {"order": ["cerebras"]}}
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["response_format"] is AssistantResponse
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


async def test_provider_exception_becomes_llm_unavailable():
    def boom(**kwargs):
        raise RuntimeError("openrouter 502")

    client = LLMClient(completion_fn=boom)
    with pytest.raises(LLMUnavailableError, match="openrouter 502"):
        await client.complete([])


async def test_malformed_provider_payload_becomes_llm_unavailable():
    def weird(**kwargs):
        return SimpleNamespace(choices=[])

    client = LLMClient(completion_fn=weird)
    with pytest.raises(LLMUnavailableError, match="malformed provider response"):
        await client.complete([])


async def test_none_content_is_returned_as_empty_string():
    completion = fake_completion(None)
    client = LLMClient(completion_fn=completion)
    assert await client.complete([]) == ""


def test_is_mock_enabled_reads_the_environment(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert is_mock_enabled() is False
    monkeypatch.setenv("LLM_MOCK", " True ")
    assert is_mock_enabled() is True
