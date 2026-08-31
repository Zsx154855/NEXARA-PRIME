"""Tests for L2 Session domain object + 7-state lifecycle."""
import pytest
from nexara_prime.session import Session, SessionStatus, SessionStore, TERMINAL_STATES


class TestSessionLifecycle:
    def test_create(self):
        s = Session.create("user_1")
        assert s.status == SessionStatus.CREATED
        assert s.user_id == "user_1"
        assert s.version == 1

    def test_valid_transition_created_to_active(self):
        s = Session.create("u")
        s.transition(SessionStatus.ACTIVE)
        assert s.status == SessionStatus.ACTIVE
        assert s.version == 2

    def test_illegal_transition_raises(self):
        s = Session.create("u")
        with pytest.raises(ValueError, match="illegal_session_transition"):
            s.transition(SessionStatus.CLOSED)

    def test_any_to_failed(self):
        s = Session.create("u")
        s.transition(SessionStatus.ACTIVE)
        s.transition(SessionStatus.FAILED)
        assert s.status == SessionStatus.FAILED

    def test_failed_is_terminal(self):
        s = Session.create("u")
        s.transition(SessionStatus.FAILED)
        with pytest.raises(ValueError):
            s.transition(SessionStatus.ACTIVE)

    def test_closed_is_terminal(self):
        s = Session.create("u")
        s.transition(SessionStatus.ACTIVE)
        s.transition(SessionStatus.CLOSED)
        with pytest.raises(ValueError):
            s.transition(SessionStatus.ACTIVE)


class TestSessionConversations:
    def test_add_conversation(self):
        s = Session.create("u")
        s.add_conversation("conv_1")
        assert "conv_1" in s.conversation_ids

    def test_dedup_conversation(self):
        s = Session.create("u")
        s.add_conversation("conv_1")
        s.add_conversation("conv_1")
        assert len(s.conversation_ids) == 1


class TestSessionStore:
    def test_create_and_get(self):
        store = SessionStore()
        s = store.create_session("u1")
        assert store.get(s.id).user_id == "u1"

    def test_get_missing_raises(self):
        store = SessionStore()
        with pytest.raises(KeyError):
            store.get("nonexistent")

    def test_list_sessions(self):
        store = SessionStore()
        store.create_session("u1")
        store.create_session("u2")
        assert len(store.list_sessions()) == 2
