"""ConnectorAuditTrail — security audit events for connector operations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..models import new_id, now_iso


@dataclass
class AuditEvent:
    audit_event_id: str = field(default_factory=lambda: new_id("aud"))
    event_type: str = ""
    timestamp: str = field(default_factory=now_iso)
    actor_id: str = ""
    actor_type: str = ""
    session_id: str = ""
    mission_id: str = ""
    connector_id: str = ""
    resource: str = ""
    action: str = ""
    decision: str = ""
    policy_id: str = ""
    risk_level: str = ""
    trace_id: str = ""
    evidence_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorAuditTrail:
    def __init__(self, store=None):
        self._store = store
        self._buffer: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self._buffer.append(event)
        if self._store:
            try:
                self._store.append_event("audit", event.__dict__)
            except Exception:
                pass

    def list_events(self, connector_id: str = "", limit: int = 50) -> list[dict]:
        events = self._buffer
        if connector_id:
            events = [e for e in events if e.connector_id == connector_id]
        return [e.__dict__ for e in events[-limit:]]

    def flush(self) -> None:
        self._buffer.clear()
