"""Tests for L2 SessionLayer — orchestration API."""
import pytest
from nexara_prime.db import SQLiteStore
from nexara_prime.session import SessionStatus
from nexara_prime.session_api import SessionLayer


@pytest.fixture
def layer(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    return SessionLayer(store)


class TestSessionLayer:
    def test_create_and_get(self, layer):
        s = layer.create_session("u1")
        loaded = layer.get_session(s.id)
        assert loaded.user_id == "u1"

    def test_update_status(self, layer):
        s = layer.create_session("u")
        updated = layer.update_session_status(s.id, "ACTIVE")
        assert updated.status == SessionStatus.ACTIVE

    def test_bind_conversation(self, layer):
        s = layer.create_session("u")
        layer.bind_conversation(s.id, "conv_1")
        convos = layer.list_conversations(s.id)
        assert "conv_1" in convos

    def test_bind_mission(self, layer):
        s = layer.create_session("u")
        layer.bind_mission(s.id, "mission_1")
        ctx = layer.load_context(s.id)
        assert "mission_1" in ctx["mission_ids"]

    def test_load_context(self, layer):
        s = layer.create_session("u")
        layer.bind_conversation(s.id, "c1")
        layer.bind_mission(s.id, "m1")
        ctx = layer.load_context(s.id)
        assert ctx["session"]["user_id"] == "u"
        assert "c1" in ctx["conversation_ids"]
        assert "m1" in ctx["mission_ids"]
