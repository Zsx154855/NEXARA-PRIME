"""Reasoning Kernel models — dataclasses for reasoning traces, decisions, confidence scores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningStep:
    """Single step in a reasoning chain."""
    step_id: str
    step_type: str  # OBSERVE, CLASSIFY, DECOMPOSE, INFER, VALIDATE, SYNTHESIZE, REFLECT
    input_facts: list[str] = field(default_factory=list)
    operation: str = ""
    output: str = ""
    confidence: float = 0.0
    evidence_refs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ReasoningTrace:
    """Full reasoning chain audit trail."""
    reasoning_id: str
    mission_id: str
    steps: list[ReasoningStep] = field(default_factory=list)
    final_confidence: float = 0.0
    self_check_passed: bool = False
    created_at: str = ""


@dataclass
class AssembledContext:
    """Context assembled from memory retrieval."""
    mission_summary: str = ""
    relevant_memories: list[dict[str, Any]] = field(default_factory=list)
    past_decisions: list[dict[str, Any]] = field(default_factory=list)
    preferences: list[dict[str, Any]] = field(default_factory=list)
    context_size: int = 0
    max_items: int = 50
    max_tokens: int = 5000


@dataclass
class DecisionOption:
    """A decision alternative with evidence."""
    option_id: str
    description: str
    evidence: list[str] = field(default_factory=list)
    predicted_outcome: str = ""
    confidence: float = 0.0


@dataclass
class Decision:
    """Governed decision output."""
    decision_id: str
    mission_id: str
    selected_option: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    risk: str = "R1"
    confidence: float = 0.0
    alternatives: list[DecisionOption] = field(default_factory=list)


@dataclass
class ConfidenceScore:
    """Confidence evaluation result."""
    score: float  # 0.0 - 1.0
    level: str  # HIGH, MEDIUM, LOW, INSUFFICIENT
    factors: dict[str, float] = field(default_factory=dict)
    uncertainty_sources: list[str] = field(default_factory=list)


@dataclass
class SelfCheckResult:
    """Self-check verification result."""
    overall_pass: bool
    checks_passed: int
    checks_total: int
    failures: list[dict[str, Any]] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)


@dataclass
class ReasoningResult:
    """Final reasoning output."""
    reasoning_id: str
    trace: ReasoningTrace
    conclusion: str
    confidence: ConfidenceScore
    evidence_refs: list[str] = field(default_factory=list)
    alternatives: list[DecisionOption] = field(default_factory=list)
    self_check: SelfCheckResult | None = None


@dataclass
class MissionContext:
    """Mission context for reasoning input."""
    mission_id: str = ""
    objective: str = ""
    risk_level: str = "R1"
    constraints: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
