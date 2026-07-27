"""NEXARA Chief Brain Kernel — Contracts (Protocols).

All brain components define Protocols here. Implementations are in sibling modules.
The Brain NEVER executes tools directly. It produces MissionContracts that the Runtime executes.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ── Core Brain Contract ────────────────────────────────────────────────────

@runtime_checkable
class BrainComponent(Protocol):
    """Every brain component must identify itself for evidence trails."""

    name: str

    def health(self) -> dict[str, Any]:
        """Return component health status."""
        ...


# ── Decision Contract ──────────────────────────────────────────────────────

class DecisionInput:
    """Input to the DecisionEngine — all facts, no opinions."""

    mission_id: str
    objective: str
    risk_level: str
    context: dict[str, Any]
    available_capabilities: list[str]
    budget_remaining: float


class DecisionOutput:
    """Output from the DecisionEngine — decisions with evidence."""

    decision_id: str
    mission_id: str
    action: str  # "execute", "delegate", "escalate", "reject"
    selected_model: str
    selected_provider: str
    reasoning: str
    risk_assessment: str
    evidence_refs: list[str]
    timestamp: str


# ── Model Policy Contract ──────────────────────────────────────────────────

class ModelPolicy:
    """Governs which model to use for which task."""

    def select_model(self, complexity: float, risk: float, context_size: int, budget: float) -> str:
        """Return model name (e.g. 'deepseek-v4-flash')."""
        ...

    def allowed_for_risk(self, model: str, risk_level: str) -> bool:
        """Check if model is allowed for this risk level."""
        ...


# ── Memory Controller Contract ─────────────────────────────────────────────

class MemoryControllerProtocol(Protocol):
    """Governs memory operations across layers."""

    def commit(
        self,
        mission_id: str,
        key: str,
        content: str,
        kind: str,  # MemoryKind value
        evidence_id: str | None = None,
    ) -> str:
        """Commit a memory with mandatory evidence binding. Returns memory_id."""
        ...

    def recall(self, mission_id: str, layer: str | None = None) -> list[dict[str, Any]]:
        """Recall memories for a mission, optionally filtered by layer."""
        ...

    def consolidate(self, mission_id: str) -> list[str]:
        """Consolidate episodic into semantic memories. Returns consolidated IDs."""
        ...

    def summary(self) -> dict[str, Any]:
        """Return memory summary with per-layer counts."""
        ...


# ── Retrieval Interface Contract (Phase 1 new) ─────────────────────────────

class RetrievalInterface(Protocol):
    """Unified memory retrieval with ranking and cross-layer query."""

    def rank_retrieve(
        self,
        query: str,
        top_k: int = 10,
        layers: list[str] | None = None,
        min_confidence: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Ranked retrieval with relevance + recency + confidence scoring."""
        ...

    def cross_layer_query(
        self, query: str, min_confidence: float = 0.3,
    ) -> dict[str, Any]:
        """Transparent query across all 4 layers. Returns grouped results."""
        ...

    def health_report(self) -> dict[str, Any]:
        """Generate memory health report."""
        ...


# ── Goal Contract ──────────────────────────────────────────────────────────

class Goal:
    """A tracked goal in the brain."""

    goal_id: str
    mission_id: str
    description: str
    status: str  # "active", "blocked", "completed", "cancelled"
    parent_goal_id: str | None
    evidence_refs: list[str]
    created_at: str
    completed_at: str | None
