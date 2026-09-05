"""Tests for profile repository functions."""

from app.db.repositories import get_cash_balance, set_cash_balance


class TestProfile:
    def test_get_default_cash_balance(self, isolated_db):
        assert get_cash_balance() == 10000.0

    def test_set_cash_balance_updates_existing_profile(self, isolated_db):
        set_cash_balance(5000.0)
        assert get_cash_balance() == 5000.0

    def test_get_cash_balance_unknown_user_defaults_to_zero(self, isolated_db):
        assert get_cash_balance(user_id="someone-else") == 0.0

    def test_set_cash_balance_creates_profile_for_new_user(self, isolated_db):
        set_cash_balance(1234.0, user_id="someone-else")
        assert get_cash_balance(user_id="someone-else") == 1234.0
        # The default user's profile is unaffected.
        assert get_cash_balance() == 10000.0
