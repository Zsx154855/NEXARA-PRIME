"""Security Audit Ledger — append-only, hash-chained audit trail."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, List

from .models import new_id, now_iso


@dataclass
class AuditEntry:
    audit_event_id: str = field(default_factory=lambda: new_id('evt'))
    event_type: str = ""
    timestamp: str = field(default_factory=now_iso)
    actor_id: str = ""
    actor_type: str = ""  # "human" | "agent" | "system"
    session_id: str = ""
    mission_id: str = ""
    connector_id: str = ""
    resource: str = ""
    action: str = ""
    decision: str = ""  # "allowed" | "blocked" | "error"
    policy_id: str = ""
    risk_level: str = ""
    trace_id: str = ""
    previous_hash: str = ""
    event_hash: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps({
            "audit_event_id": self.audit_event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "session_id": self.session_id,
            "mission_id": self.mission_id,
            "connector_id": self.connector_id,
            "resource": self.resource,
            "action": self.action,
            "decision": self.decision,
            "policy_id": self.policy_id,
            "risk_level": self.risk_level,
            "trace_id": self.trace_id,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


class SecurityAuditLedger:
    """Append-only, hash-chained. Every entry links to previous entry's hash."""

    def __init__(self, store=None):
        self._entries: list[AuditEntry] = []
        self._store = store
        self._last_hash: str = "0" * 64  # genesis hash

    def record(self, event_type: str, actor_id: str = "", actor_type: str = "system",
               session_id: str = "", mission_id: str = "", connector_id: str = "",
               resource: str = "", action: str = "", decision: str = "allowed",
               policy_id: str = "", risk_level: str = "", trace_id: str = "",
               metadata: dict | None = None) -> AuditEntry:
        entry = AuditEntry(
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            session_id=session_id,
            mission_id=mission_id,
            connector_id=connector_id,
            resource=resource,
            action=action,
            decision=decision,
            policy_id=policy_id,
            risk_level=risk_level,
            trace_id=trace_id,
            previous_hash=self._last_hash,
        )
        entry.event_hash = entry.compute_hash()
        self._entries.append(entry)
        self._last_hash = entry.event_hash
        if self._store:
            try:
                self._store.append_event("security_audit", entry.__dict__)
            except Exception:
                pass
        return entry

    def verify_chain(self) -> tuple[bool, str]:
        """Verify hash chain integrity."""
        expected = "0" * 64
        for i, entry in enumerate(self._entries):
            if entry.previous_hash != expected:
                return False, f"chain broken at entry {i}: expected prev_hash={expected[:16]}..., got {entry.previous_hash[:16]}..."
            computed = entry.compute_hash()
            if computed != entry.event_hash:
                return False, f"hash mismatch at entry {i}: stored={entry.event_hash[:16]}..., computed={computed[:16]}..."
            expected = computed
        return True, f"chain intact: {len(self._entries)} entries verified"

    def detect_tamper(self) -> list[int]:
        """Return indices of tampered entries."""
        tampered = []
        expected = "0" * 64
        for i, entry in enumerate(self._entries):
            if entry.previous_hash != expected:
                tampered.append(i)
            elif entry.compute_hash() != entry.event_hash:
                tampered.append(i)
            expected = entry.event_hash
        return tampered

    def count(self) -> int:
        return len(self._entries)

    def list_entries(self, limit: int = 50, event_type: str = "") -> list[dict]:
        entries = self._entries
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        return [e.__dict__ for e in entries[-limit:]]

    def get_entry(self, audit_event_id: str) -> AuditEntry | None:
        for e in self._entries:
            if e.audit_event_id == audit_event_id:
                return e
        return None

    def missing_events(self) -> int:
        """Detect gaps in the chain — entries removed from the middle."""
        if len(self._entries) < 2:
            return 0
        missing = 0
        expected = self._entries[0].event_hash
        for i in range(1, len(self._entries)):
            if self._entries[i].previous_hash != expected:
                missing += 1
            expected = self._entries[i].event_hash
        return missing
