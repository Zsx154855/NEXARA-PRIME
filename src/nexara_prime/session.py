"""Independent Session domain object + 7-state lifecycle.

Session is a first-class domain concept, distinct from Conversation and from
the permission-scoped ``SessionIdentity`` in :mod:`identity`. A Session owns
zero or more conversations (``conversation_ids``); a conversation is NOT an
alias for a session — the two have different ids, lifecycles, and owners.

No Core files are imported or modified beyond the shared ``new_id``/``now_iso``
helpers from :mod:`models`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .models import new_id, now_iso

__all__ = [
    "Session",
    "SessionStatus",
    "SessionStore",
    "TRANSITIONS",
    "TERMINAL_STATES",
]


class SessionStatus(str, enum.Enum):
    """Seven-state session lifecycle."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    RECOVERING = "RECOVERING"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


# Legal transitions. ``FAILED`` is additionally reachable from any state.
TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.CREATED: frozenset({SessionStatus.ACTIVE}),
    SessionStatus.ACTIVE: frozenset({
        SessionStatus.IDLE,
        SessionStatus.SUSPENDED,
        SessionStatus.RECOVERING,
        SessionStatus.CLOSED,
    }),
    SessionStatus.IDLE: frozenset({SessionStatus.ACTIVE}),
    SessionStatus.RECOVERING: frozenset({SessionStatus.ACTIVE}),
    SessionStatus.SUSPENDED: frozenset({SessionStatus.ACTIVE}),
    SessionStatus.CLOSED: frozenset(),
    SessionStatus.FAILED: frozenset(),
}

TERMINAL_STATES: frozenset[SessionStatus] = frozenset(
    {SessionStatus.CLOSED, SessionStatus.FAILED}
)


def _can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    """``any -> FAILED`` is always legal; otherwise consult TRANSITIONS."""
    if target is SessionStatus.FAILED:
        return current is not SessionStatus.FAILED
    return target in TRANSITIONS.get(current, frozenset())


@dataclass
class Session:
    """A sovereign session domain object.

    Owns conversations via ``conversation_ids``; identity is the session id,
    never a conversation id.
    """

    id: str = field(default_factory=lambda: new_id("session"))
    user_id: str = ""  # owner
    created_at: str = field(default_factory=now_iso)
    last_activity: str = field(default_factory=now_iso)
    status: SessionStatus = SessionStatus.CREATED
    version: int = 1
    conversation_ids: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, user_id: str) -> "Session":
        """Create a new session in the CREATED state."""
        return cls(user_id=user_id)

    def _bump(self) -> None:
        self.version += 1
        self.last_activity = now_iso()

    def transition(self, target: SessionStatus) -> "Session":
        """Advance the state machine, raising on illegal transitions."""
        if not _can_transition(self.status, target):
            raise ValueError(
                f"illegal_session_transition:{self.status.value}->{target.value}"
            )
        if target is not self.status:
            self.status = target
            self._bump()
        return self

    def touch(self) -> "Session":
        """Record activity without a state change."""
        self._bump()
        return self

    def add_conversation(self, conversation_id: str) -> "Session":
        """Bind a conversation to this session (deduplicated, ordered)."""
        if conversation_id not in self.conversation_ids:
            self.conversation_ids.append(conversation_id)
            self._bump()
        return self


class SessionStore:
    """In-memory Session repository.

    Mirrors the local-first ``IdentityStore`` shape: create / update_status /
    touch / add_conversation. Does not alias session to conversation.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self, user_id: str) -> Session:
        session = Session.create(user_id=user_id)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError(f"session_not_found:{session_id}")
        return self._sessions[session_id]

    def update_status(self, session_id: str, status: SessionStatus) -> Session:
        session = self.get(session_id)
        session.transition(status)
        return session

    def touch(self, session_id: str) -> Session:
        session = self.get(session_id)
        session.touch()
        return session

    def add_conversation(self, session_id: str, conversation_id: str) -> Session:
        session = self.get(session_id)
        session.add_conversation(conversation_id)
        return session

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())
