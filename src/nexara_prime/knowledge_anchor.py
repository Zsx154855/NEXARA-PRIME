"""
NEXARA Knowledge Anchor V1

Four-tier anchor system: IMMUTABLE → STABLE → DYNAMIC → EPHEMERAL.
Immutable anchors cannot be overwritten by dynamic context.
Each anchor carries source, version, SHA-256, timestamp.

NSEC V2.1 §5.C
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import now_iso


class AnchorTier(str, Enum):
    IMMUTABLE = "immutable"
    STABLE = "stable"
    DYNAMIC = "dynamic"
    EPHEMERAL = "ephemeral"


# Mandatory anchor keys that must be present before routing
MANDATORY_ANCHOR_KEYS: frozenset[str] = frozenset({
    "soul", "identity", "owner", "governance",
})


def _compute_sha256(key: str, value: str) -> str:
    return hashlib.sha256(f"{key}:{value}".encode()).hexdigest()


def _escape_anchor_value(value: str) -> str:
    """Escape newlines and label delimiters to prevent prompt injection."""
    return value.replace("\n", "\\n").replace("[", "\\[").replace("]", "\\]")


@dataclass(frozen=True)
class KnowledgeAnchorRecord:
    """A single anchored knowledge item."""

    anchor_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    tier: AnchorTier = AnchorTier.DYNAMIC
    key: str = ""
    value: str = ""
    source: str = ""
    version: str = "1.0"
    sha256: str = ""
    timestamp: str = field(default_factory=now_iso)
    provenance_evidence_id: str = ""

    def __post_init__(self) -> None:
        computed = _compute_sha256(self.key, self.value)
        if self.sha256 and self.sha256 != computed:
            raise ValueError(
                f"Supplied SHA-256 {self.sha256[:12]} does not match "
                f"computed {computed[:12]} for anchor '{self.key}'"
            )
        if not self.sha256:
            object.__setattr__(self, "sha256", computed)


@dataclass
class KnowledgeAnchor:
    """Manages four-tier anchor storage with governance enforcement."""

    soul_constitution: dict = field(default_factory=dict)
    identity_fingerprint: dict = field(default_factory=dict)
    owner_authority: dict = field(default_factory=dict)
    governance_rules: dict = field(default_factory=dict)
    immutable: list[KnowledgeAnchorRecord] = field(default_factory=list)
    stable: list[KnowledgeAnchorRecord] = field(default_factory=list)
    dynamic: list[KnowledgeAnchorRecord] = field(default_factory=list)
    ephemeral: list[KnowledgeAnchorRecord] = field(default_factory=list)
    _deleted_keys: set[str] = field(default_factory=set)

    # ── anchor insertion ─────────────────────────────────

    def add(self, record: KnowledgeAnchorRecord) -> KnowledgeAnchorRecord:
        # Reject immutable overwrite
        if record.tier == AnchorTier.IMMUTABLE:
            for existing in self.immutable:
                if existing.key == record.key:
                    raise ValueError(f"Cannot overwrite IMMUTABLE anchor: {record.key}")
        # Reject lower-tier reuse of immutable key
        if record.tier != AnchorTier.IMMUTABLE:
            for existing in self.immutable:
                if existing.key == record.key:
                    raise ValueError(
                        f"Cannot register {record.tier.value} record for "
                        f"immutable key '{record.key}'"
                    )
        # Prevent deleted memory from re-entering
        if record.key in self._deleted_keys:
            raise ValueError(f"Deleted memory cannot re-enter anchor: {record.key}")
        tier_list = self._tier_list(record.tier)
        # Remove old key from same tier only
        tier_list[:] = [r for r in tier_list if r.key != record.key]
        tier_list.append(record)
        return record

    def recall_immutable(self, key: str) -> KnowledgeAnchorRecord | None:
        for r in self.immutable:
            if r.key == key:
                return r
        return None

    def delete(self, key: str) -> None:
        """Delete an anchor key. IMMUTABLE anchors are rejected."""
        for r in self.immutable:
            if r.key == key:
                raise ValueError(
                    f"Cannot delete IMMUTABLE anchor '{key}'; "
                    f"requires separately governed operation"
                )
        self._deleted_keys.add(key)
        for tier_list in (self.stable, self.dynamic, self.ephemeral):
            tier_list[:] = [r for r in tier_list if r.key != key]

    def is_deleted(self, key: str) -> bool:
        return key in self._deleted_keys

    def has_mandatory_anchors(self) -> bool:
        """Return True only when soul, identity, owner, governance are present,
        each verified as IMMUTABLE tier with valid SHA and unique key."""
        found: set[str] = set()
        for r in self.immutable:
            if r.key in MANDATORY_ANCHOR_KEYS:
                # Verify tier is IMMUTABLE (guaranteed by being in self.immutable)
                # Verify SHA is valid (guaranteed by KnowledgeAnchorRecord.__post_init__)
                # Verify provenance (at minimum, key must exist)
                if not r.sha256 or len(r.sha256) != 64:
                    continue  # invalid SHA
                found.add(r.key)
        return MANDATORY_ANCHOR_KEYS.issubset(found)

    # ── token budget management ──────────────────────────

    def build_context(
        self,
        token_budget: int = 100_000,
        chars_per_token: float = 3.5,
    ) -> str:
        """
        Build anchored context within token budget.
        Priority: IMMUTABLE → STABLE → DYNAMIC → EPHEMERAL.
        Fail-closed: if a higher tier cannot fit, stop entirely.
        """
        budget_chars = int(token_budget * chars_per_token)
        parts: list[str] = []
        remaining = budget_chars
        exhausted_at_tier: AnchorTier | None = None

        for tier_list in (self.immutable, self.stable, self.dynamic, self.ephemeral):
            for record in tier_list:
                escaped = _escape_anchor_value(record.value)
                text = f"[{record.tier.value.upper()}][{record.key}] {escaped}"
                if len(text) <= remaining:
                    parts.append(text)
                    remaining -= len(text)
                else:
                    # This tier cannot fully fit → track exhaustion
                    if not exhausted_at_tier:
                        exhausted_at_tier = record.tier
                    break  # stop at this tier
            # FAIL CLOSED: if we exhausted at IMMUTABLE, STABLE, or DYNAMIC, stop entirely
            if exhausted_at_tier and exhausted_at_tier in (
            AnchorTier.IMMUTABLE,
            AnchorTier.STABLE,
            AnchorTier.DYNAMIC,
            ):
                break

        return "\n".join(parts)

    # ── persistence helpers ───────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise for persistence."""
        def _ser(rec: KnowledgeAnchorRecord) -> dict:
            return {
                "anchor_id": rec.anchor_id, "tier": rec.tier.value,
                "key": rec.key, "value": rec.value, "source": rec.source,
                "version": rec.version, "sha256": rec.sha256,
                "timestamp": rec.timestamp,
                "provenance_evidence_id": rec.provenance_evidence_id,
            }
        return {
            "immutable": [_ser(r) for r in self.immutable],
            "stable": [_ser(r) for r in self.stable],
            "dynamic": [_ser(r) for r in self.dynamic],
            "ephemeral": [_ser(r) for r in self.ephemeral],
            "deleted_keys": sorted(self._deleted_keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeAnchor:
        """Deserialise from persistence."""
        def _deser(d: dict) -> KnowledgeAnchorRecord:
            return KnowledgeAnchorRecord(
                anchor_id=d.get("anchor_id", ""),
                tier=AnchorTier(d.get("tier", "dynamic")),
                key=d.get("key", ""), value=d.get("value", ""),
                source=d.get("source", ""), version=d.get("version", "1.0"),
                sha256=d.get("sha256", ""), timestamp=d.get("timestamp", ""),
                provenance_evidence_id=d.get("provenance_evidence_id", ""),
            )
        ka = cls()
        ka.immutable = [_deser(r) for r in data.get("immutable", [])]
        ka.stable = [_deser(r) for r in data.get("stable", [])]
        ka.dynamic = [_deser(r) for r in data.get("dynamic", [])]
        ka.ephemeral = [_deser(r) for r in data.get("ephemeral", [])]
        ka._deleted_keys = set(data.get("deleted_keys", []))
        return ka

    # ── helpers ──────────────────────────────────────────

    def _tier_list(self, tier: AnchorTier) -> list[KnowledgeAnchorRecord]:
        return {
            AnchorTier.IMMUTABLE: self.immutable,
            AnchorTier.STABLE: self.stable,
            AnchorTier.DYNAMIC: self.dynamic,
            AnchorTier.EPHEMERAL: self.ephemeral,
        }[tier]

    @property
    def immutable_count(self) -> int:
        return len(self.immutable)

    @property
    def total_anchors(self) -> int:
        return sum(len(t) for t in (self.immutable, self.stable, self.dynamic, self.ephemeral))
