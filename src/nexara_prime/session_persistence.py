"""L2 Session persistence adapter — SQLite-backed Session repository."""
from __future__ import annotations

from typing import Any

from .db import SQLiteStore
from .session import Session, SessionStatus

__all__ = ["SQLiteSessionStore"]

SESSION_RECORD_TYPE = "session"


class SQLiteSessionStore:
    """SQLite-backed Session store. Reuses the Session domain object and
    persists each session as a 'session' record in the durable store."""

    def __init__(self, store: SQLiteStore):
        self._store = store

    @staticmethod
    def _dump(s: Session) -> dict[str, Any]:
        return {
            "session_id": s.id,
            "user_id": s.user_id,
            "created_at": s.created_at,
            "last_activity": s.last_activity,
            "status": s.status.value,
            "version": s.version,
            "conversation_ids": list(s.conversation_ids),
        }

    @staticmethod
    def _load(p: dict[str, Any]) -> Session:
        return Session(
            id=p["session_id"],
            user_id=p.get("user_id", ""),
            created_at=p["created_at"],
            last_activity=p.get("last_activity", p.get("created_at", "")),
            status=SessionStatus(p["status"]),
            version=int(p.get("version", 1)),
            conversation_ids=list(p.get("conversation_ids", [])),
        )

    def _persist(self, s: Session) -> None:
        self._store.save_record(s.id, SESSION_RECORD_TYPE, self._dump(s), s.created_at, None)

    def create_session(self, user_id: str) -> Session:
        s = Session.create(user_id=user_id)
        self._persist(s)
        return s

    def get(self, session_id: str) -> Session:
        p = self._store.get_record(session_id)
        if p is None:
            raise KeyError(f"session_not_found:{session_id}")
        return self._load(p)

    def update_status(self, session_id: str, status: SessionStatus) -> Session:
        s = self.get(session_id)
        s.transition(status)
        self._persist(s)
        return s

    def touch(self, session_id: str) -> Session:
        s = self.get(session_id)
        s.touch()
        self._persist(s)
        return s

    def add_conversation(self, session_id: str, conversation_id: str) -> Session:
        s = self.get(session_id)
        s.add_conversation(conversation_id)
        self._persist(s)
        return s

    def list_sessions(self) -> list[Session]:
        return [self._load(p) for p in self._store.list_records(SESSION_RECORD_TYPE)]
