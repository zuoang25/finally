"""Structured-output parsing must never raise (CONTRACTS.md section 5.2)."""

import json

from app.llm.schemas import (
    MISSING_MESSAGE_TEXT,
    UNPARSEABLE_MESSAGE,
    AssistantResponse,
    ChatTurn,
    Trade,
    parse_assistant_response,
)


def test_parses_a_valid_response():
    raw = json.dumps(
        {
            "message": "Bought some NVDA.",
            "trades": [{"ticker": "NVDA", "side": "buy", "quantity": 5}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    parsed = parse_assistant_response(raw)

    assert parsed.message == "Bought some NVDA."
    assert parsed.trades[0].ticker == "NVDA"
    assert parsed.trades[0].side == "buy"
    assert parsed.trades[0].quantity == 5.0
    assert parsed.watchlist_changes[0].action == "add"


def test_defaults_are_empty_lists():
    parsed = parse_assistant_response('{"message":"Just chatting."}')
    assert parsed.trades == []
    assert parsed.watchlist_changes == []


def test_defaults_are_not_shared_between_instances():
    first = AssistantResponse(message="a")
    first.trades.append(Trade(ticker="AAPL", side="buy", quantity=1))
    assert AssistantResponse(message="b").trades == []


def test_malformed_json_degrades():
    parsed = parse_assistant_response('{"message": "truncated", "trades": [')
    assert parsed.message
    assert parsed.trades == []
    assert parsed.watchlist_changes == []


def test_plain_prose_becomes_the_message():
    parsed = parse_assistant_response("Your portfolio is up 3% today.")
    assert parsed.message == "Your portfolio is up 3% today."
    assert parsed.trades == []


def test_empty_response_degrades():
    assert parse_assistant_response("").message == UNPARSEABLE_MESSAGE
    assert parse_assistant_response(None).message == UNPARSEABLE_MESSAGE


def test_missing_message_with_actions_gets_placeholder_text():
    raw = json.dumps({"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]})
    parsed = parse_assistant_response(raw)

    assert parsed.message == MISSING_MESSAGE_TEXT
    assert len(parsed.trades) == 1


def test_missing_message_without_actions_gets_fallback_text():
    parsed = parse_assistant_response(json.dumps({"trades": []}))
    assert parsed.message == UNPARSEABLE_MESSAGE


def test_invalid_action_entries_are_dropped_not_fatal():
    raw = json.dumps(
        {
            "message": "Mixed bag.",
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 1},
                {"ticker": "MSFT", "side": "hodl", "quantity": 1},
                "not-an-object",
            ],
            "watchlist_changes": [
                {"ticker": "PYPL", "action": "add"},
                {"ticker": "X", "action": "sideways"},
            ],
        }
    )
    parsed = parse_assistant_response(raw)

    assert [t.ticker for t in parsed.trades] == ["AAPL"]
    assert [c.ticker for c in parsed.watchlist_changes] == ["PYPL"]


def test_wrong_types_for_action_lists_are_ignored():
    raw = json.dumps({"message": "hi", "trades": "nope", "watchlist_changes": 7})
    parsed = parse_assistant_response(raw)
    assert parsed.message == "hi"
    assert parsed.trades == []


def test_fenced_json_is_unwrapped():
    raw = '```json\n{"message": "Fenced.", "trades": []}\n```'
    assert parse_assistant_response(raw).message == "Fenced."


def test_json_embedded_in_prose_is_extracted():
    raw = 'Sure thing! {"message": "Embedded.", "trades": []} Hope that helps.'
    assert parse_assistant_response(raw).message == "Embedded."


def test_chat_turn_to_dict_matches_the_wire_shape():
    turn = ChatTurn(message="hi", actions=[{"type": "trade"}], created_at="2026-09-05T10:00:00Z")
    assert turn.to_dict() == {
        "message": "hi",
        "actions": [{"type": "trade"}],
        "created_at": "2026-09-05T10:00:00Z",
    }
