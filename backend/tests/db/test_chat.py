"""Tests for chat message repository functions."""

from app.db.repositories import add_chat_message, list_chat_messages


class TestChat:
    def test_add_user_message_has_no_actions(self, isolated_db):
        row = add_chat_message("user", "buy me 5 nvidia")
        assert row.role == "user"
        assert row.content == "buy me 5 nvidia"
        assert row.actions is None

    def test_actions_round_trip_through_json(self, isolated_db):
        actions = [
            {"type": "trade", "status": "executed", "ticker": "NVDA", "side": "buy"},
            {"type": "watchlist", "status": "executed", "ticker": "PYPL", "action": "add"},
        ]
        row = add_chat_message("assistant", "Bought 5 NVDA.", actions=actions)
        assert row.actions == actions

        fetched = [m for m in list_chat_messages() if m.id == row.id][0]
        assert fetched.actions == actions

    def test_none_actions_round_trips_as_none(self, isolated_db):
        add_chat_message("user", "hello", actions=None)
        row = list_chat_messages()[0]
        assert row.actions is None

    def test_list_chat_messages_oldest_first(self, isolated_db):
        add_chat_message("user", "first")
        add_chat_message("assistant", "second")
        add_chat_message("user", "third")
        contents = [m.content for m in list_chat_messages()]
        assert contents == ["first", "second", "third"]

    def test_list_chat_messages_respects_limit(self, isolated_db):
        for i in range(5):
            add_chat_message("user", f"msg {i}")
        assert len(list_chat_messages(limit=2)) == 2

    def test_chat_row_to_dict_keys(self, isolated_db):
        row = add_chat_message("user", "hello")
        assert set(row.to_dict().keys()) == {
            "id",
            "user_id",
            "role",
            "content",
            "actions",
            "created_at",
        }
