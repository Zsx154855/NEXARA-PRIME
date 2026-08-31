"""Agent Session Layer orchestration API (L2).

Wraps :class:`SQLiteSessionStore` with a thin orchestration surface:
``create_session`` / ``get_session`` / ``update_session_status`` /
``bind_conversation`` / ``list_conversations`` / ``bind_mission`` /
``load_context``. No V1.0 Core file is imported or modified.

``mission_ids`` is maintained at this layer (``Session`` has no such field)
and persisted as an auxiliary record so it survives restart recovery.
"""

from __future__ import annotations

from typing import Any

from .db import SQLiteStore
from .session import Session, SessionStatus
from .session_persistence import SQLiteSessionStore

__all__ = ["SessionLayer"]

_MISSION_BINDING_RECORD_TYPE = "session_mission_bindings"


def _mission_record_id(session_id: str) -> str:
    return f"{session_id}#missions"


def _coerce_status(status: SessionStatus | str) -> SessionStatus:
    if isinstance(status, SessionStatus):
        return status
    return SessionStatus(status)


class SessionLayer:
    """Agent Session Layer orchestration API backed by SQLiteSessionStore."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._sessions = SQLiteSessionStore(store)

    # -- mission_ids helpers (maintained at this layer) --

    def _load_mission_ids(self, session_id: str) -> list[str]:
        p = self._store.get_record(_mission_record_id(session_id))
        if p:
            return list(p.get("mission_ids", []))
        return []

    def _persist_mission_ids(self, session_id: str, mission_ids: list[str]) -> None:
        s = self._sessions.get(session_id)
        self._store.save_record(
            _mission_record_id(session_id),
            _MISSION_BINDING_RECORD_TYPE,
            {"session_id": session_id, "mission_ids": list(mission_ids)},
            s.created_at,
            None,
        )

    # -- public API --

    def create_session(self, user_id: str) -> Session:
        return self._sessions.create_session(user_id)

    def get_session(self, session_id: str) -> Session:
        return self._sessions.get(session_id)

    def update_session_status(
        self, session_id: str, status: SessionStatus | str
    ) -> Session:
        return self._sessions.update_status(session_id, _coerce_status(status))

    def bind_conversation(self, session_id: str, conversation_id: str) -> Session:
        return self._sessions.add_conversation(session_id, conversation_id)

    def list_conversations(self, session_id: str) -> list[str]:
        return list(self._sessions.get(session_id).conversation_ids)

    def bind_mission(self, session_id: str, mission_id: str) -> Session:
        self._sessions.get(session_id)  # raise KeyError if session missing
        mission_ids = self._load_mission_ids(session_id)
        if mission_id not in mission_ids:
            mission_ids.append(mission_id)
            self._persist_mission_ids(session_id, mission_ids)
        return self._sessions.get(session_id)

    def load_context(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        return {
            "session": {
                "session_id": session.id,
                "user_id": session.user_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "status": session.status.value,
                "version": session.version,
            },
            "conversation_ids": list(session.conversation_ids),
            "mission_ids": self._load_mission_ids(session_id),
        }
