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
    fallback_entries: list[ModelPortfolioEntry] = field(default_factory=list)
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
    MIN_COUNCIL_MEMBERS = 2
    MAX_VERIFIER_ATTEMPTS = 2

    def __init__(self, registry: ModelPortfolioRegistry):
        self.registry = registry
        self.profiler = MissionIntelligenceProfiler()
        self.builder = DynamicPromptBuilder()

    def route(
        self, mission: dict, anchors: KnowledgeAnchor, force_mode: str = ""
    ) -> RouteResult:
        profile = self.profiler.profile(mission)
        mode = (
            OrchestrationMode(force_mode) if force_mode
            else self._derive_mode(profile)
        )

        # Mandatory governance anchors check
        if not anchors.has_mandatory_anchors():
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                reason="Missing mandatory governance anchors — fail closed",
            )

        # Get ALL entries for rejection reporting, then filter to production
        all_entries = self.registry.list_all()
        candidates = self.registry.list_production()
        if not candidates:
            # Build rejection for every entry
            rejected_ids = []
            rejected_map = {}
            for e in all_entries:
                why = self._check_entry(e, profile)
                if why:
                    rejected_ids.append(e.portfolio_id)
                    rejected_map[e.portfolio_id] = why
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                rejected_entries=rejected_ids,
                rejection_reasons=rejected_map,
                reason="No real provider available — fail closed",
            )

        # Sort: recommended tier first, then reliability
        candidates.sort(
            key=lambda e: (
                0 if e.tier == profile.recommended_tier else 1,
                -e.capability.reliability_score,
            )
        )

        # Filter by profile requirements — evaluate ALL entries for rejections
        rejected: dict[str, str] = {}
        eligible = self._filter_candidates(candidates, profile, rejected)

        # Also report why non-candidates were rejected
        for e in all_entries:
            if e.portfolio_id not in {c.portfolio_id for c in candidates}:
                why = self._check_entry(e, profile)
                if why and e.portfolio_id not in rejected:
                    rejected[e.portfolio_id] = why

        if not eligible:
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                rejected_entries=list(rejected.keys()),
                rejection_reasons=rejected,
                reason="No eligible provider after filtering",
            )

        # Gate approval-required missions
        if profile.owner_approval_required:
            return RouteResult(
                mode=OrchestrationMode.HUMAN_ESCALATION,
                reason="Owner approval required but not yet granted",
                approved=False,
            )

        return self._build_result(mode, eligible, profile, rejected)

    # ── mode derivation ──────────────────────────────────

    def _derive_mode(self, profile: MissionIntelligenceProfile) -> OrchestrationMode:
        strategy = profile.recommended_strategy
        mode_map = {
            "DIRECT_SINGLE": OrchestrationMode.DIRECT_SINGLE,
            "FLASH_THEN_PRO": OrchestrationMode.FLASH_THEN_PRO,
            "PRO_WITH_VERIFIER": OrchestrationMode.PRO_WITH_VERIFIER,
            "SEQUENTIAL_RELAY": OrchestrationMode.SEQUENTIAL_RELAY,
            "PARALLEL_COUNCIL": OrchestrationMode.PARALLEL_COUNCIL,
            "SPECIALIST_DELEGATION": OrchestrationMode.SPECIALIST_DELEGATION,
        }
        return mode_map.get(strategy, OrchestrationMode.DIRECT_SINGLE)

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

    def _check_entry(
        self, entry: ModelPortfolioEntry, profile: MissionIntelligenceProfile
    ) -> str:
        if entry.is_mock:
            return "mock_provider"
        if entry.health in (ModelHealth.UNHEALTHY, ModelHealth.DISABLED):
            return f"health_{entry.health.value}"
        if not entry.enabled:
            return "disabled"
        # Compare mission context_size with provider max_context_tokens
        ctx_size = profile.context_size
        if ctx_size > 0 and ctx_size > entry.capability.max_context_tokens:
            return f"context_insufficient (need {ctx_size}, have {entry.capability.max_context_tokens})"
        if profile.privacy_required and entry.sovereignty.value == "cloud_global":
            return "privacy_incompatible"
        if (
            profile.tool_use_requirement.value in ("required", "critical")
            and not entry.capability.supports_tools
        ):
            return "tool_incompatible"
        # Honor latency constraints
        if (
            profile.latency_target_ms > 0
            and entry.capability.typical_latency_ms > profile.latency_target_ms
        ):
            return (
                f"latency_exceeded "
                f"(target={profile.latency_target_ms}ms, "
                f"entry={entry.capability.typical_latency_ms}ms)"
            )
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
        fallback_chain: list[ModelPortfolioEntry] = []

        if mode == OrchestrationMode.PRO_WITH_VERIFIER:
            if len(eligible) >= 2:
                primary = eligible[0]
                verifier = (
                    eligible[1]
                    if eligible[1].portfolio_id != primary.portfolio_id
                    else None
                )
            if verifier is None:
                # Fail closed: no independent verifier available
                return RouteResult(
                    mode=OrchestrationMode.HUMAN_ESCALATION,
                    rejected_entries=list(rejected.keys()),
                    rejection_reasons=rejected,
                    reason="PRO_WITH_VERIFIER requested but no independent verifier available",
                )
        elif mode == OrchestrationMode.PARALLEL_COUNCIL:
            # Require at least 2 distinct models
            distinct = []
            seen_ids = set()
            for e in eligible:
                if e.portfolio_id not in seen_ids:
                    distinct.append(e)
                    seen_ids.add(e.portfolio_id)
                if len(distinct) >= self.MAX_COUNCIL_MEMBERS:
                    break
            if len(distinct) < self.MIN_COUNCIL_MEMBERS:
                return RouteResult(
                    mode=OrchestrationMode.HUMAN_ESCALATION,
                    rejected_entries=list(rejected.keys()),
                    rejection_reasons=rejected,
                    reason=f"PARALLEL_COUNCIL requires ≥{self.MIN_COUNCIL_MEMBERS} distinct models, only {len(distinct)} available",
                )
            council = distinct
            primary = council[0]
        elif mode == OrchestrationMode.FLASH_THEN_PRO:
            # Stage chain: flash first, then pro
            flash_candidates = [e for e in eligible if e.tier == 1]
            pro_candidates = [e for e in eligible if e.tier >= 2]
            if not flash_candidates or not pro_candidates:
                return RouteResult(
                    mode=OrchestrationMode.HUMAN_ESCALATION,
                    reason="FLASH_THEN_PRO requires both flash and pro candidates",
                )
            primary = flash_candidates[0]
            fallback_chain = pro_candidates
        elif mode == OrchestrationMode.FAILOVER:
            if len(eligible) < 2:
                return RouteResult(
                    mode=OrchestrationMode.HUMAN_ESCALATION,
                    reason="FAILOVER requires at least 2 eligible candidates",
                )
            primary = eligible[0]
            fallback_chain = eligible[1:]
        elif mode == OrchestrationMode.SEQUENTIAL_RELAY:
            if len(eligible) < 2:
                return RouteResult(
                    mode=OrchestrationMode.HUMAN_ESCALATION,
                    reason="SEQUENTIAL_RELAY requires at least 2 eligible candidates",
                )
            fallback_chain = eligible[:-1]
            primary = eligible[-1]  # strongest last

        return RouteResult(
            mode=mode,
            primary_entry=primary,
            verifier_entry=verifier,
            council_entries=council,
            fallback_entries=fallback_chain,
            rejected_entries=list(rejected.keys()),
            rejection_reasons=rejected,
            reason=f"Routed via {mode.value}",
        )
