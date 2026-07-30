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

from .models import now_iso


class AnchorTier(str, Enum):
    IMMUTABLE = "immutable"
    STABLE = "stable"
    DYNAMIC = "dynamic"
    EPHEMERAL = "ephemeral"


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

    def __post_init__(self):
        if not self.sha256:
            object.__setattr__(self, "sha256", hashlib.sha256(
                f"{self.key}:{self.value}".encode()
            ).hexdigest())


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
        tier_list = self._tier_list(record.tier)
        # Enforce immutability: IMMUTABLE records cannot be overwritten
        if record.tier == AnchorTier.IMMUTABLE:
            for existing in self.immutable:
                if existing.key == record.key:
                    raise ValueError(f"Cannot overwrite IMMUTABLE anchor: {record.key}")
        # Prevent deleted memory from re-entering
        if record.key in self._deleted_keys:
            raise ValueError(f"Deleted memory cannot re-enter anchor: {record.key}")
        # Remove old key from same tier
        tier_list[:] = [r for r in tier_list if r.key != record.key]
        tier_list.append(record)
        return record

    def recall_immutable(self, key: str) -> KnowledgeAnchorRecord | None:
        for r in self.immutable:
            if r.key == key:
                return r
        return None

    def delete(self, key: str) -> None:
        self._deleted_keys.add(key)
        for tier_list in (self.immutable, self.stable, self.dynamic, self.ephemeral):
            tier_list[:] = [r for r in tier_list if r.key != key]

    def is_deleted(self, key: str) -> bool:
        return key in self._deleted_keys

    # ── token budget management ──────────────────────────

    def build_context(
        self,
        token_budget: int = 100_000,
        chars_per_token: float = 3.5,
    ) -> str:
        """
        Build anchored context within token budget.
        Priority: IMMUTABLE → STABLE → DYNAMIC → EPHEMERAL.
        """
        budget_chars = int(token_budget * chars_per_token)
        parts: list[str] = []
        remaining = budget_chars

        for tier_list in (self.immutable, self.stable, self.dynamic, self.ephemeral):
            for record in tier_list:
                text = f"[{record.tier.value.upper()}][{record.key}] {record.value}"
                if len(text) <= remaining:
                    parts.append(text)
                    remaining -= len(text)
                else:
                    break  # stop at this tier
            if remaining <= 0:
                break

        return "\n".join(parts)

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
