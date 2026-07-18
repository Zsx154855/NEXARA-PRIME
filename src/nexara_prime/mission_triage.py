from __future__ import annotations

from .models import (
    AdaptiveMode,
    MissionTriageResult,
    now_iso,
)


class MissionDecisionRecord:
    """Human-readable decision record explaining each scoring dimension."""

    def __init__(self, mission_id: str, intent: str) -> None:
        self.mission_id = mission_id
        self.intent = intent
        self.reasons: list[str] = []
        self.dimensions: dict[str, str] = {}

    def add_dimension(self, name: str, value: float, reasoning: str) -> None:
        self.dimensions[name] = f"{value:.3f} — {reasoning}"
        self.reasons.append(f"{name}: {reasoning}")


class MissionTriageEngine:
    """Evaluates a mission's complexity, risk, and uncertainty to recommend an
    adaptive mode (S0–S3), required model tier, governance level, and roles.

    The scoring algorithm uses a weighted-linear approach over multiple factors
    rather than shallow keyword matching.  Every decision is recorded in a
    MissionDecisionRecord for auditability.
    """

    # ── Weights ──────────────────────────────────────────────────────────────
    _W_EXT_SIDE_EFFECTS = 0.25
    _W_UNCERTAINTY = 0.15
    _W_TOOL_COUNT = 0.15
    _W_DATA_SENSITIVITY = 0.15
    _W_REVERSIBILITY = 0.10
    _W_DURATION = 0.10
    _W_EVIDENCE_LEVEL = 0.05
    _W_TOKEN_COST = 0.05

    _SENSITIVITY_WEIGHTS = {
        "none": 0.0,
        "low": 0.2,
        "medium": 0.5,
        "high": 0.8,
        "critical": 1.0,
    }

    _EVIDENCE_WEIGHTS = {
        "none": 0.0,
        "minimal": 0.1,
        "standard": 0.3,
        "thorough": 0.6,
        "exhaustive": 1.0,
    }

    def triage(
        self,
        intent: str,
        context: str,
        requested_outcome: str,
        tool_requirements: list[str],
        data_sensitivity: str = "low",
        external_side_effects: bool = False,
        reversibility: bool = True,
        uncertainty: float = 0.0,
        expected_duration: int = 0,
        expected_token_cost: int = 0,
        required_evidence_level: str = "minimal",
        mission_id: str | None = None,
    ) -> MissionTriageResult:
        """Run the full triage pipeline and return a MissionTriageResult."""
        record = MissionDecisionRecord(mission_id or "unknown", intent)

        # ── 1. Score each dimension ─────────────────────────────────────────
        complexity_score = self._compute_complexity(
            tool_requirements, uncertainty, expected_duration, expected_token_cost, record
        )
        risk_score = self._compute_risk(
            external_side_effects, reversibility, data_sensitivity, complexity_score, record
        )
        uncertainty_score = self._compute_uncertainty(uncertainty, record)

        # ── 2. Map scores to mode ───────────────────────────────────────────
        recommended_mode, escalation_conditions = self._recommend_mode(
            complexity_score, risk_score, uncertainty_score,
            external_side_effects, reversibility, record,
        )

        # ── 3. Derive supporting fields ─────────────────────────────────────
        required_roles = self._derive_roles(recommended_mode, tool_requirements)
        required_model_tier = self._derive_model_tier(complexity_score, risk_score)
        required_governance_level = self._derive_governance(risk_score, data_sensitivity)
        required_evidence_tier = self._derive_evidence_tier(recommended_mode, risk_score)

        # ── 4. Cost estimate ────────────────────────────────────────────────
        expected_cost = self._estimate_cost(
            expected_token_cost, recommended_mode, tool_requirements,
        )

        # ── 5. Build result ─────────────────────────────────────────────────
        result = MissionTriageResult(
            mission_id=mission_id or "",
            intent=intent,
            context_summary=context[:500] if context else "",
            requested_outcome=requested_outcome,
            tool_requirements=tool_requirements,
            data_sensitivity=data_sensitivity,
            external_side_effects=external_side_effects,
            reversibility=reversibility,
            uncertainty=uncertainty,
            expected_duration_ms=expected_duration,
            expected_token_cost=expected_token_cost,
            required_evidence_level=required_evidence_level,
            complexity_score=complexity_score,
            risk_score=risk_score,
            uncertainty_score=uncertainty_score,
            expected_cost=expected_cost,
            recommended_mode=recommended_mode.value,
            required_roles=required_roles,
            required_model_tier=required_model_tier,
            required_governance_level=required_governance_level,
            required_evidence_tier=required_evidence_tier,
            escalation_conditions=escalation_conditions,
            decision_reasoning="\n".join(record.reasons),
            created_at=now_iso(),
        )
        return result

    # ── Dimension scoring ────────────────────────────────────────────────────

    def _compute_complexity(
        self,
        tool_requirements: list[str],
        uncertainty: float,
        expected_duration: int,
        expected_token_cost: int,
        record: MissionDecisionRecord,
    ) -> float:
        """Complexity rises with tool count, uncertainty, duration, and token
        cost — each is normalised and weighted."""
        n_tools = len(tool_requirements)
        tool_factor = min(1.0, n_tools / 10.0)  # 10+ tools = max
        dur_factor = min(1.0, expected_duration / 600_000)  # 10 min = max
        token_factor = min(1.0, expected_token_cost / 500_000)

        raw = (
            self._W_TOOL_COUNT * tool_factor
            + self._W_UNCERTAINTY * min(1.0, uncertainty)
            + self._W_DURATION * dur_factor
            + self._W_TOKEN_COST * token_factor
        )
        # normalise to [0,1] via division by sum of weights for these dimensions
        normaliser = (
            self._W_TOOL_COUNT + self._W_UNCERTAINTY
            + self._W_DURATION + self._W_TOKEN_COST
        )
        score = min(1.0, raw / normaliser) if normaliser > 0 else 0.0

        record.add_dimension(
            "complexity", score,
            f"tools={n_tools} (factor={tool_factor:.2f}), "
            f"uncertainty={uncertainty:.2f}, "
            f"duration={expected_duration}ms (factor={dur_factor:.2f}), "
            f"token_cost={expected_token_cost} (factor={token_factor:.2f})",
        )
        return round(score, 4)

    def _compute_risk(
        self,
        external_side_effects: bool,
        reversibility: bool,
        data_sensitivity: str,
        complexity_score: float,
        record: MissionDecisionRecord,
    ) -> float:
        """Risk is heavily driven by external side effects, then data
        sensitivity and irreversibility, with a modest bump from complexity."""
        ext_factor = 1.0 if external_side_effects else 0.0
        rev_factor = 0.0 if reversibility else 0.7
        sens_factor = self._SENSITIVITY_WEIGHTS.get(data_sensitivity, 0.2)

        raw = (
            self._W_EXT_SIDE_EFFECTS * ext_factor
            + self._W_REVERSIBILITY * rev_factor
            + self._W_DATA_SENSITIVITY * sens_factor
            + 0.10 * complexity_score  # complexity adds a modest risk bump
        )
        normaliser = (
            self._W_EXT_SIDE_EFFECTS + self._W_REVERSIBILITY
            + self._W_DATA_SENSITIVITY + 0.10
        )
        score = min(1.0, raw / normaliser) if normaliser > 0 else 0.0

        record.add_dimension(
            "risk", score,
            f"external_side_effects={external_side_effects} (factor={ext_factor:.2f}), "
            f"reversible={reversibility} (factor={rev_factor:.2f}), "
            f"data_sensitivity={data_sensitivity} (factor={sens_factor:.2f}), "
            f"complexity_bump={complexity_score:.4f}",
        )
        return round(score, 4)

    def _compute_uncertainty(self, uncertainty: float, record: MissionDecisionRecord) -> float:
        """Uncertainty is a pass-through of the raw user-provided value,
        clamped to [0,1]."""
        score = min(1.0, max(0.0, uncertainty))
        record.add_dimension(
            "uncertainty", score,
            f"raw_uncertainty={uncertainty:.2f} (clamped)",
        )
        return round(score, 4)

    # ── Mode recommendation ──────────────────────────────────────────────────

    def _recommend_mode(
        self,
        complexity: float,
        risk: float,
        uncertainty: float,
        external_side_effects: bool,
        reversibility: bool,
        record: MissionDecisionRecord,
    ) -> tuple[AdaptiveMode, list[str]]:
        """Map scores to an adaptive mode.

        Rules:
          S0 — simple, low-risk, single-step, no external effects
          S1 — limited reasoning, may use one tool, low uncertainty
          S2 — multi-step, multi-tool, medium uncertainty
          S3 — high risk, irreversible, external side effects, complex multi-agent
        """
        escalation: list[str] = []

        if external_side_effects and not reversibility and risk >= 0.6:
            mode = AdaptiveMode.S3
            escalation.append("Irreversible external side effects detected")
        elif risk >= 0.65 or complexity >= 0.65:
            mode = AdaptiveMode.S3
            escalation.append("High risk or complexity threshold exceeded")
        elif risk >= 0.45 or complexity >= 0.45 or uncertainty >= 0.5:
            mode = AdaptiveMode.S2
            if uncertainty >= 0.5:
                escalation.append("High uncertainty requires monitored execution")
        elif complexity >= 0.25 or risk >= 0.20 or uncertainty >= 0.20:
            mode = AdaptiveMode.S1
        else:
            mode = AdaptiveMode.S0

        # Safety valve: external side effects always push to at least S2
        if external_side_effects and mode not in (AdaptiveMode.S3,):
            escalation.append("External side effects override — escalated to S3")
            mode = AdaptiveMode.S3

        if not reversibility and mode.value < "S2":
            escalation.append("Irreversible operation requires at least S2")
            mode = AdaptiveMode.S2

        mode_order = {"S3": 3, "S2": 2, "S1": 1, "S0": 0}
        record.add_dimension(
            "recommended_mode",
            float(mode_order.get(mode.value, 0)),
            f"complexity={complexity:.4f}, risk={risk:.4f}, uncertainty={uncertainty:.4f}"
            f" → {mode.value}",
        )
        return mode, escalation

    # ── Derived fields ───────────────────────────────────────────────────────

    def _derive_roles(self, mode: AdaptiveMode, tools: list[str]) -> list[str]:
        """Map mode to required runtime roles."""
        base = ["Orchestrator", "Executor"]
        if mode == AdaptiveMode.S0:
            return base
        roles = ["Orchestrator", "Planner", "Executor", "Reviewer"]
        if mode == AdaptiveMode.S2:
            roles += ["Auditor"]
        if mode == AdaptiveMode.S3:
            roles += ["Auditor", "Archivist", "Analyst"]
        # If research-like tools are present, add Researcher
        if any("search" in t.lower() or "read" in t.lower() or "research" in t.lower() for t in tools):
            roles.append("Researcher")
        return list(dict.fromkeys(roles))

    def _derive_model_tier(self, complexity: float, risk: float) -> str:
        """Flash for simple/standard, pro for complex/high-risk."""
        if complexity >= 0.4 or risk >= 0.4:
            return "pro"
        return "flash"

    def _derive_governance(self, risk: float, data_sensitivity: str) -> str:
        """Governance level based on risk and data sensitivity."""
        if risk >= 0.6 or data_sensitivity in ("critical", "high"):
            return "strict"
        elif risk >= 0.3 or data_sensitivity == "medium":
            return "standard"
        return "relaxed"

    def _derive_evidence_tier(self, mode: AdaptiveMode, risk: float) -> str:
        """Evidence requirements scale with mode and risk."""
        if mode == AdaptiveMode.S3 or risk >= 0.5:
            return "exhaustive"
        elif mode == AdaptiveMode.S2 or risk >= 0.3:
            return "thorough"
        elif mode == AdaptiveMode.S1:
            return "standard"
        return "minimal"

    def _estimate_cost(
        self,
        token_cost: int,
        mode: AdaptiveMode,
        tools: list[str],
    ) -> float:
        """Simple cost estimate based on token cost, mode overhead, and tool
        count overhead."""
        mode_multiplier = {
            AdaptiveMode.S0: 1.0,
            AdaptiveMode.S1: 1.5,
            AdaptiveMode.S2: 2.5,
            AdaptiveMode.S3: 4.0,
        }
        tool_overhead = 1.0 + (len(tools) * 0.05)
        return round(
            (token_cost / 1_000_000.0) * mode_multiplier.get(mode, 1.0) * tool_overhead,
            6,
        )
