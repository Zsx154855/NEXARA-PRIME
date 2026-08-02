"""Phase 3 Cognitive Intelligence — shared models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningDecision:
    decision_id: str
    mission_id: str
    normalized_goal: str
    constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    candidate_strategies: list[dict[str, Any]] = field(default_factory=list)
    selected_strategy: str = ""
    rejected_strategies: list[str] = field(default_factory=list)
    risk_analysis: dict[str, float] = field(default_factory=dict)
    expected_outcomes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    uncertainty: float = 0.5
    unresolved_questions: list[str] = field(default_factory=list)
    escalation_required: bool = False
    created_at: str = ""


@dataclass
class StrategicPlan:
    plan_id: str
    owner_goal: str
    success_criteria: list[str] = field(default_factory=list)
    planning_horizon: str = ""
    strategies: list[dict[str, Any]] = field(default_factory=list)
    missions: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, str]] = field(default_factory=list)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    resource_requirements: dict[str, Any] = field(default_factory=dict)
    risks: list[dict[str, Any]] = field(default_factory=list)
    approval_points: list[str] = field(default_factory=list)
    fallback_paths: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: str = "DRAFT"


@dataclass
class WorldEntity:
    id: str
    type: str
    source: str
    provenance: str = ""
    observed_at: str = ""
    valid_from: str = ""
    valid_until: str = ""
    freshness: float = 1.0
    confidence: float = 0.5
    evidence_refs: list[str] = field(default_factory=list)
    classification: str = "FACT"


@dataclass
class CognitiveAssessment:
    assessment_id: str
    mission_id: str
    known_facts: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    confidence: float = 0.5
    uncertainty_sources: list[str] = field(default_factory=list)
    contradiction_count: int = 0
    calibration_score: float = 0.5
    recommended_action: str = ""
    human_escalation_required: bool = False
    created_at: str = ""


@dataclass
class ResearchTask:
    research_id: str
    question: str
    scope: str = ""
    exclusions: list[str] = field(default_factory=list)
    source_requirements: list[str] = field(default_factory=list)
    freshness_requirement: str = ""
    budget_limit: int = 0
    time_limit: int = 0
    approval_requirements: list[str] = field(default_factory=list)
    status: str = "DRAFT"
