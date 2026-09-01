"""Tests for L2 SQLiteSessionStore — SQLite-backed Session repository."""
import pytest
from nexara_prime.db import SQLiteStore
from nexara_prime.session import SessionStatus
from nexara_prime.session_persistence import SQLiteSessionStore


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(str(tmp_path / "test.db"))


@pytest.fixture
def session_store(store):
    return SQLiteSessionStore(store)


class TestSQLiteSessionStore:
    def test_create_and_get(self, session_store):
        s = session_store.create_session("user_1")
        loaded = session_store.get(s.id)
        assert loaded.user_id == "user_1"
        assert loaded.status == SessionStatus.CREATED

    def test_update_status(self, session_store):
        s = session_store.create_session("u")
        updated = session_store.update_status(s.id, SessionStatus.ACTIVE)
        assert updated.status == SessionStatus.ACTIVE
        assert updated.version == 2

    def test_add_conversation(self, session_store):
        s = session_store.create_session("u")
        updated = session_store.add_conversation(s.id, "conv_1")
        assert "conv_1" in updated.conversation_ids

    def test_persistence_survives_reload(self, store):
        ss1 = SQLiteSessionStore(store)
        s = ss1.create_session("u")
        ss2 = SQLiteSessionStore(store)
        loaded = ss2.get(s.id)
        assert loaded.user_id == "u"

    def test_get_missing_raises(self, session_store):
        with pytest.raises(KeyError):
            session_store.get("nonexistent")
