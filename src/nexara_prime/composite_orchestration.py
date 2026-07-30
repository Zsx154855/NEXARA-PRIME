"""
NEXARA Composite Orchestration Engine V1

Supports 8 orchestration modes: DIRECT_SINGLE, FLASH_THEN_PRO, PRO_WITH_VERIFIER,
SEQUENTIAL_RELAY, PARALLEL_COUNCIL, SPECIALIST_DELEGATION, FAILOVER, HUMAN_ESCALATION.

NSEC V2.1 §5.E
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .dynamic_prompt_builder import DynamicPromptBuilder
from .knowledge_anchor import KnowledgeAnchor
from .mission_intelligence_profiler import (
    MissionIntelligenceProfile,
    MissionIntelligenceProfiler,
)
from .model_portfolio_registry import (
    ModelHealth,
    ModelPortfolioEntry,
    ModelPortfolioRegistry,
)


class OrchestrationMode(str, Enum):
    DIRECT_SINGLE = "DIRECT_SINGLE"
    FLASH_THEN_PRO = "FLASH_THEN_PRO"
    PRO_WITH_VERIFIER = "PRO_WITH_VERIFIER"
    SEQUENTIAL_RELAY = "SEQUENTIAL_RELAY"
    PARALLEL_COUNCIL = "PARALLEL_COUNCIL"
    SPECIALIST_DELEGATION = "SPECIALIST_DELEGATION"
    FAILOVER = "FAILOVER"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"


@dataclass
class RouteRequest:
    mission: dict
    profile: MissionIntelligenceProfile
    anchors: KnowledgeAnchor


@dataclass
class RouteResult:
    route_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mode: OrchestrationMode = OrchestrationMode.DIRECT_SINGLE
    primary_entry: ModelPortfolioEntry | None = None
    verifier_entry: ModelPortfolioEntry | None = None
    council_entries: list[ModelPortfolioEntry] = field(default_factory=list)
    rejected_entries: list[str] = field(default_factory=list)
    rejection_reasons: dict[str, str] = field(default_factory=dict)
    fallback: RouteResult | None = None
    approved: bool = False
    reason: str = ""


class CompositeOrchestrationEngine:
    """
    Routes missions to models based on profile, portfolio, and governance.
    No mock in production. No fake council. No unbounded retry.
    """

    MAX_ROUTE_ATTEMPTS = 3
    MAX_COUNCIL_MEMBERS = 3
    MAX_VERIFIER_ATTEMPTS = 2

    def __init__(self, registry: ModelPortfolioRegistry):
        self.registry = registry
        self.profiler = MissionIntelligenceProfiler()
        self.builder = DynamicPromptBuilder()

    def route(self, mission: dict, anchors: KnowledgeAnchor, force_mode: str = "") -> RouteResult:
        profile = self.profiler.profile(mission)
        mode = OrchestrationMode(force_mode) if force_mode else self._derive_mode(profile)

        # Get production candidates (no mock, no disabled, no unhealthy)
        candidates = self.registry.list_production()
        if not candidates:
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                reason="No real provider available — fail closed",
            )

        # Sort by tier then capability fit
        candidates.sort(key=lambda e: (-e.tier, -e.capability.reliability_score))

        # Filter by profile requirements
        rejected: dict[str, str] = {}
        eligible = self._filter_candidates(candidates, profile, rejected)

        if not eligible:
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                rejected_entries=[e.portfolio_id for e in candidates],
                rejection_reasons=rejected,
                reason="No eligible provider after filtering",
            )

        return self._build_result(mode, eligible, profile, rejected)

    # ── mode derivation ──────────────────────────────────

    def _derive_mode(self, profile: MissionIntelligenceProfile) -> OrchestrationMode:
        if profile.owner_approval_required:
            return OrchestrationMode.PRO_WITH_VERIFIER
        return {
            "DIRECT_SINGLE": OrchestrationMode.DIRECT_SINGLE,
            "FLASH_THEN_PRO": OrchestrationMode.FLASH_THEN_PRO,
            "PRO_WITH_VERIFIER": OrchestrationMode.PRO_WITH_VERIFIER,
            "SEQUENTIAL_RELAY": OrchestrationMode.SEQUENTIAL_RELAY,
            "PARALLEL_COUNCIL": OrchestrationMode.PARALLEL_COUNCIL,
            "SPECIALIST_DELEGATION": OrchestrationMode.SPECIALIST_DELEGATION,
        }.get(profile.recommended_strategy, OrchestrationMode.DIRECT_SINGLE)

    # ── candidate filtering ───────────────────────────────

    def _filter_candidates(
        self,
        candidates: list[ModelPortfolioEntry],
        profile: MissionIntelligenceProfile,
        rejected: dict[str, str],
    ) -> list[ModelPortfolioEntry]:
        eligible: list[ModelPortfolioEntry] = []
        for entry in candidates:
            why = self._check_entry(entry, profile)
            if why:
                rejected[entry.portfolio_id] = why
            else:
                eligible.append(entry)
        return eligible

    def _check_entry(self, entry: ModelPortfolioEntry, profile: MissionIntelligenceProfile) -> str:
        if entry.is_mock:
            return "mock_provider"
        if entry.health == ModelHealth.UNHEALTHY:
            return "unhealthy"
        if not entry.enabled:
            return "disabled"
        if profile.token_budget > entry.capability.max_context_tokens:
            return "context_insufficient"
        if profile.privacy_required and entry.sovereignty.value == "cloud_global":
            return "privacy_incompatible"
        if profile.tool_use_requirement.value in ("required", "critical") and not entry.capability.supports_tools:
            return "tool_incompatible"
        return ""

    # ── result construction ────────────────────────────────

    def _build_result(
        self,
        mode: OrchestrationMode,
        eligible: list[ModelPortfolioEntry],
        profile: MissionIntelligenceProfile,
        rejected: dict[str, str],
    ) -> RouteResult:
        primary = eligible[0] if eligible else None
        verifier = None
        council: list[ModelPortfolioEntry] = []

        if mode == OrchestrationMode.PRO_WITH_VERIFIER and len(eligible) >= 2:
            primary = eligible[0]
            verifier = eligible[1] if eligible[1].portfolio_id != primary.portfolio_id else eligible[0]
        elif mode == OrchestrationMode.PARALLEL_COUNCIL:
            council = eligible[:self.MAX_COUNCIL_MEMBERS]
            primary = council[0] if council else None
        elif mode == OrchestrationMode.SEQUENTIAL_RELAY:
            primary = eligible[-1]  # strongest last

        return RouteResult(
            mode=mode,
            primary_entry=primary,
            verifier_entry=verifier,
            council_entries=council,
            rejected_entries=list(rejected.keys()),
            rejection_reasons=rejected,
            reason=f"Routed via {mode.value}",
        )
