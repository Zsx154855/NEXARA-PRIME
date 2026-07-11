"""Security Audit Ledger — append-only, hash-chained, persisted via SQLiteStore.
P0-5: Empty ledger + missions = FAIL. Full mission lifecycle coverage."""
from __future__ import annotations

import hashlib, json
from dataclasses import dataclass, field
from typing import Any

from .models import new_id, now_iso


@dataclass
class AuditEntry:
    audit_event_id: str = field(default_factory=lambda: new_id("aud"))
    event_type: str = ""
    timestamp: str = field(default_factory=now_iso)
    actor_id: str = ""
    actor_type: str = ""
    session_id: str = ""
    mission_id: str = ""
    task_id: str = ""
    connector_id: str = ""
    resource: str = ""
    action: str = ""
    decision: str = ""
    policy_id: str = ""
    risk_level: str = ""
    trace_id: str = ""
    previous_hash: str = ""
    event_hash: str = ""
    payload_hash: str = ""
    metadata: dict = field(default_factory=dict)

    def compute_hash(self) -> str:
        payload = json.dumps({
            "audit_event_id": self.audit_event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "session_id": self.session_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
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
    """Append-only, hash-chained. Persisted via SQLiteStore."""

    def __init__(self, store=None):
        self._store = store
        self._entries: list[AuditEntry] = []
        self._last_hash: str = "0" * 64
        self._load_from_store()

    def _load_from_store(self) -> None:
        if not self._store:
            return
        try:
            raw_entries = self._store.list_records("audit_entry")
            for raw in raw_entries:
                entry = AuditEntry(**{k: v for k, v in raw.items()
                                       if k in AuditEntry.__dataclass_fields__})
                self._entries.append(entry)
            if self._entries:
                self._last_hash = self._entries[-1].event_hash
        except Exception:
            pass

    def record(self, event_type: str, actor_id: str = "", actor_type: str = "system",
               session_id: str = "", mission_id: str = "", task_id: str = "",
               connector_id: str = "", resource: str = "", action: str = "",
               decision: str = "allowed", policy_id: str = "", risk_level: str = "",
               trace_id: str = "", metadata: dict | None = None) -> AuditEntry:
        entry = AuditEntry(
            event_type=event_type, actor_id=actor_id, actor_type=actor_type,
            session_id=session_id, mission_id=mission_id, task_id=task_id,
            connector_id=connector_id, resource=resource, action=action,
            decision=decision, policy_id=policy_id, risk_level=risk_level,
            trace_id=trace_id, previous_hash=self._last_hash,
            metadata=metadata or {},
        )
        entry.payload_hash = hashlib.sha256(json.dumps(entry.__dict__, sort_keys=True, default=str).encode()).hexdigest()[:16]
        entry.event_hash = entry.compute_hash()
        self._entries.append(entry)
        self._last_hash = entry.event_hash

        if self._store:
            try:
                self._store.save_record(entry.audit_event_id, "audit_entry",
                                         entry.__dict__, entry.timestamp)
            except Exception:
                pass
        return entry

    def verify_chain(self) -> tuple[bool, str]:
        if not self._entries:
            return True, "chain empty (0 entries)"
        expected = "0" * 64
        for i, entry in enumerate(self._entries):
            if entry.previous_hash != expected:
                return False, f"chain broken at entry {i}"
            computed = entry.compute_hash()
            if computed != entry.event_hash:
                return False, f"hash mismatch at entry {i}"
            expected = computed
        return True, f"chain intact: {len(self._entries)} entries"

    def verify_with_mission_check(self, has_missions: bool = False) -> tuple[bool, str]:
        chain_ok, chain_msg = self.verify_chain()
        if has_missions and len(self._entries) == 0:
            return False, "FAIL: missions exist but audit chain is empty"
        if not chain_ok:
            return chain_ok, chain_msg
        return True, chain_msg

    def detect_tamper(self) -> list[int]:
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

    def list_entries(self, limit: int = 50, event_type: str = "",
                      mission_id: str = "") -> list[dict]:
        entries = self._entries
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if mission_id:
            entries = [e for e in entries if e.mission_id == mission_id]
        return [e.__dict__ for e in entries[-limit:]]

    def get_entry(self, audit_event_id: str) -> AuditEntry | None:
        for e in self._entries:
            if e.audit_event_id == audit_event_id:
                return e
        return None

    def missing_events(self) -> int:
        if len(self._entries) < 2:
            return 0
        missing = 0
        expected = self._entries[0].event_hash
        for i in range(1, len(self._entries)):
            if self._entries[i].previous_hash != expected:
                missing += 1
            expected = self._entries[i].event_hash
        return missing
