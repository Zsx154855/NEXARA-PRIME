"""
NEXARA Mission Intelligence Profiler V1

Analyses mission characteristics and produces a MissionIntelligenceProfile
that guides model routing, strategy selection, and governance decisions.

NSEC V2.1 §5.B
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .models import now_iso


class Difficulty(str, Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class Uncertainty(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Impact(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Reversibility(str, Enum):
    FULLY_REVERSIBLE = "fully_reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class SkillRequirement(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"
    CRITICAL = "critical"


@dataclass(frozen=True)
class MissionIntelligenceProfile:
    """Output of the profiler — guides routing, strategy, governance."""

    profile_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mission_id: str = ""
    # core dimensions
    difficulty: Difficulty = Difficulty.MEDIUM
    uncertainty: Uncertainty = Uncertainty.MEDIUM
    impact: Impact = Impact.MEDIUM
    reversibility: Reversibility = Reversibility.PARTIALLY_REVERSIBLE
    # skill requirements
    factuality_requirement: SkillRequirement = SkillRequirement.REQUIRED
    creativity_requirement: SkillRequirement = SkillRequirement.NONE
    coding_requirement: SkillRequirement = SkillRequirement.NONE
    research_requirement: SkillRequirement = SkillRequirement.NONE
    tool_use_requirement: SkillRequirement = SkillRequirement.NONE
    verification_requirement: SkillRequirement = SkillRequirement.REQUIRED
    # constraints
    latency_target_ms: int = 10_000
    token_budget: int = 100_000
    privacy_required: bool = False
    owner_approval_required: bool = False
    # recommended strategy
    recommended_strategy: str = "DIRECT_SINGLE"
    recommended_tier: int = 2
    # metadata
    created_at: str = field(default_factory=now_iso)


class MissionIntelligenceProfiler:
    """Analyses a mission and produces a routing profile."""

    def profile(self, mission: dict) -> MissionIntelligenceProfile:
        """Derive profile from mission characteristics."""
        obj = mission.get("objective", "")
        complexity = mission.get("complexity", "medium")
        risk = mission.get("risk_level", "medium")
        ctx_size = mission.get("context_size", 0) or 0
        latency = mission.get("latency_target_ms", 0) or 10_000
        budget = mission.get("token_budget", 0) or 100_000
        tools = mission.get("tool_requirement", "none")
        approval = mission.get("owner_approval_required", False)
        mission_id = mission.get("mission_id", "")
        # difficulty
        diff_map = {"trivial": Difficulty.TRIVIAL, "low": Difficulty.LOW,
                     "medium": Difficulty.MEDIUM, "high": Difficulty.HIGH, "extreme": Difficulty.EXTREME}
        difficulty = diff_map.get(complexity, Difficulty.MEDIUM)
        # impact
        imp_map = {"none": Impact.NONE, "low": Impact.LOW, "medium": Impact.MEDIUM,
                   "high": Impact.HIGH, "critical": Impact.CRITICAL}
        impact = imp_map.get(risk, Impact.MEDIUM)
        # uncertainty
        if "unknown" in obj.lower():
            uncertainty = Uncertainty.HIGH
        elif complexity in ("high", "extreme"):
            uncertainty = Uncertainty.MEDIUM
        else:
            uncertainty = Uncertainty.LOW
        # tool requirement
        tool_map = {"none": SkillRequirement.NONE, "optional": SkillRequirement.OPTIONAL,
                    "required": SkillRequirement.REQUIRED, "critical": SkillRequirement.CRITICAL}
        tool_req = tool_map.get(tools, SkillRequirement.NONE)
        # recommended strategy
        strategy, tier = self._choose_strategy(difficulty, impact, uncertainty, approval, ctx_size)
        return MissionIntelligenceProfile(
            mission_id=mission_id,
            difficulty=difficulty,
            uncertainty=uncertainty,
            impact=impact,
            factuality_requirement=SkillRequirement.REQUIRED,
            coding_requirement=SkillRequirement.REQUIRED if "code" in obj.lower() or "fix" in obj.lower() else SkillRequirement.NONE,
            tool_use_requirement=tool_req,
            verification_requirement=SkillRequirement.REQUIRED if impact in (Impact.HIGH, Impact.CRITICAL) else SkillRequirement.OPTIONAL,
            latency_target_ms=latency,
            token_budget=budget,
            privacy_required=mission.get("privacy_required", False),
            owner_approval_required=approval,
            recommended_strategy=strategy,
            recommended_tier=tier,
        )

    @staticmethod
    def _choose_strategy(
        difficulty: Difficulty,
        impact: Impact,
        uncertainty: Uncertainty,
        owner_approval: bool,
        context_size: int,
    ) -> tuple[str, int]:
        # Context overflow → pro (check FIRST — overrides flash)
        if context_size > 32_000:
            return "DIRECT_SINGLE", 2  # pro

        # High impact → Pro + verifier
        if impact in (Impact.HIGH, Impact.CRITICAL):
            return "PRO_WITH_VERIFIER", 2

        # S0/S1 + low risk → flash
        if difficulty in (Difficulty.TRIVIAL, Difficulty.LOW) and impact in (Impact.NONE, Impact.LOW) and not owner_approval:
            return "DIRECT_SINGLE", 1  # flash

        # High uncertainty → pro
        if uncertainty == Uncertainty.HIGH:
            return "DIRECT_SINGLE", 2  # pro

        # Context overflow → pro
        if context_size > 32_000:
            return "DIRECT_SINGLE", 2  # pro

        # Owner approval → pro
        if owner_approval:
            return "PRO_WITH_VERIFIER", 2

        # Default: pro
        return "DIRECT_SINGLE", 2
