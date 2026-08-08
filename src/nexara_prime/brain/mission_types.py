"""Mission Types — frozen data types for Phase 4A Mission Intelligence Engine.

All 7 types defined here per implementation contract V3. No Pydantic models,
no models.py modifications. Pure Python dataclasses for zero-dependency use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Step 1: parse_intent ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class IntentResult:
    """Structured intent from raw user goal."""
    goal_type: str  # CODE_GEN|RESEARCH|REFACTOR|DEPLOY|AUDIT|RECOVERY|UNKNOWN
    entities: list[str] = field(default_factory=list)
    priority: str = "medium"  # low|medium|high|critical
    domain: str = ""
    raw_tokens: list[str] = field(default_factory=list)


# ── Step 2: classify_mission ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ClassificationResult:
    """Mission classification with confidence and fallback."""
    mission_type: str  # CODE_GEN|RESEARCH|REFACTOR|DEPLOY|AUDIT|RECOVERY|UNKNOWN
    confidence: float = 0.0
    fallback: str = ""
    evidence_refs: list[str] = field(default_factory=list)


# ── Step 3: decompose_goal ───────────────────────────────────────────────────

@dataclass(frozen=True)
class TaskNode:
    """A single task in a mission decomposition."""
    task_id: str
    description: str
    estimated_effort: str = "medium"  # low|medium|high
    dependencies: list[str] = field(default_factory=list)
    order: int = 0


@dataclass(frozen=True)
class DependencyEdge:
    """Dependency relationship between two tasks."""
    from_task: str
    to_task: str
    type: str = "sequential"  # sequential|parallel|conditional


@dataclass(frozen=True)
class DecompositionResult:
    """Goal decomposition into ordered task sequence."""
    tasks: list[TaskNode] = field(default_factory=list)
    dependencies: list[DependencyEdge] = field(default_factory=list)
    estimated_effort: str = "medium"
    parallel_groups: list[list[str]] = field(default_factory=list)
    source: str = "generated"  # pattern_matched|generated|fallback_linear


# ── Step 4: assess_risk ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskAssessment:
    """Risk assessment with R0-R4 classification."""
    risk_level: str  # R0|R1|R2|R3|R4
    risk_score: float = 0.0
    risk_factors: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    approval_required: bool = False
    source: str = "computed"  # computed|historical_pattern|default_R2


# ── Step 5: compile_contract ─────────────────────────────────────────────────

@dataclass(frozen=True)
class MissionContract:
    """Compiled mission contract — final artifact before kernel submission."""
    mission_id: str
    objective: str
    success_criteria: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    risk_level: str = "R2"  # R0-R4
    approval_required: bool = True
    contract_sha256: str = ""
    compiled_at: str = ""
