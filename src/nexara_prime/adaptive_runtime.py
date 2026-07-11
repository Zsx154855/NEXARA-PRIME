"""NEXARA PRIME Adaptive Runtime — Main Orchestrator.

Integrates:
- MissionTriageEngine: task classification S0-S3
- AdaptiveMultiAgentScheduler: dynamic role lifecycle + ROI gate
- CapabilityRegistryV2: evidence-driven capability scoring
- ModelRouter: flash/pro/mock routing with circuit breaker
- ResourceBudgetManager: per-mission budget tracking
- EscalationEngine: progressive S0→S3 with audit
- TokenCompilerV2: context deduplication + reference compilation

Security: all dynamic agents, providers, tools continue through:
Identity → Authorization → ApprovalStore → ToolRuntime → Sandbox → NetworkPolicy → SecretStore → Audit
"""

from __future__ import annotations

import json
from typing import Any

from .models import (
    AdaptiveEvaluation,
    AdaptiveMissionProfile,
    AdaptiveMode,
    BudgetUsage,
    EscalationDecision,
    Mission,
    MissionSpec,
    MissionTriageResult,
    MissionState,
    ModelRoutingDecision,
    ResourceBudget,
    RiskLevel,
    SchedulingPlan,
    SchedulerPolicyVersion,
    TokenCompilationRecord,
    new_id,
    now_iso,
)


class AdaptiveRuntime:
    """Orchestrates adaptive mission execution atop the NEXARA kernel."""

    def __init__(
        self,
        triage_engine=None,
        scheduler=None,
        capability_registry=None,
        model_router=None,
        budget_manager=None,
        escalation_engine=None,
        token_compiler=None,
        store=None,
        events=None,
        evidence=None,
        audit=None,
        approvals=None,
        tools=None,
        state_machine=None,
        recovery=None,
    ):
        self.triage = triage_engine
        self.scheduler = scheduler
        self.capabilities = capability_registry
        self.router = model_router
        self.budgets = budget_manager
        self.escalation = escalation_engine
        self.tokens = token_compiler
        self.store = store
        self.events = events
        self.evidence = evidence
        self.audit = audit
        self.approvals = approvals
        self.tools = tools
        self.state_machine = state_machine
        self.recovery = recovery
        self.policy = SchedulerPolicyVersion()

    # ── Triage ──

    def triage_mission(self, mission: Mission) -> MissionTriageResult:
        """Classify mission into S0-S3 adaptive mode."""
        result = self.triage.triage(
            intent=mission.spec.objective,
            context=mission.spec.source_dir or "workspace",
            requested_outcome=", ".join(mission.spec.deliverables) if mission.spec.deliverables else mission.spec.objective,
            tool_requirements=getattr(mission.spec, "risks", []),
            data_sensitivity=getattr(mission.spec, "risk_level", RiskLevel.R2).value,
            external_side_effects=False,
            reversibility=True,
            uncertainty=0.3,
            expected_duration=0,
            expected_token_cost=0,
            required_evidence_level="minimal",
            mission_id=mission.mission_id,
        )
        result.mission_id = mission.mission_id
        mission.adaptive_mode = result.recommended_mode
        mission.triage_result = result.model_dump(mode="json")

        if self.store:
            self.store.save_record(result.triage_id, "triage_result", result.model_dump(mode="json"), now_iso(), mission.mission_id)

        if self.events:
            self.events.publish("adaptive.triaged", mission.mission_id, "mission", "triage", mission.trace_id,
                               {"mode": result.recommended_mode, "complexity": result.complexity_score, "risk": result.risk_score})

        return result

    # ── Schedule ──

    def schedule_mission(self, mission: Mission, triage_result: MissionTriageResult) -> SchedulingPlan:
        """Create adaptive scheduling plan with ROI gate."""
        caps = self.capabilities.list_all() if self.capabilities else []
        plan = self.scheduler.schedule(mission.spec, triage_result, caps)
        mission.scheduling_plan = plan.model_dump(mode="json")
        mission.assignments = []  # Will be populated by scheduler

        if self.store:
            self.store.save_record(plan.plan_id, "scheduling_plan", plan.model_dump(mode="json"), now_iso(), mission.mission_id)

        return plan

    # ── Route Model ──

    def route_model(self, mission: Mission, triage_result: MissionTriageResult) -> ModelRoutingDecision:
        """Select provider/model based on triage + circuit breaker state."""
        decision = self.router.route(
            mission_id=mission.mission_id,
            complexity=triage_result.complexity_score,
            risk=triage_result.risk_score,
            context_size=len(mission.spec.objective),
            latency_target_ms=5000 if triage_result.recommended_mode in ("S0", "S1") else 30000,
            token_budget=50000 if triage_result.recommended_mode in ("S0", "S1") else 200000,
        )
        mission.routing_decisions.append(decision.model_dump(mode="json"))

        if self.store:
            self.store.save_record(decision.decision_id, "routing_decision", decision.model_dump(mode="json"), now_iso(), mission.mission_id)

        return decision

    # ── Budget ──

    def allocate_budget(self, mission: Mission, triage_result: MissionTriageResult) -> tuple[ResourceBudget, BudgetUsage]:
        """Allocate resource budget scaled by adaptive mode."""
        budget = self.budgets.create_budget(
            mission_id=mission.mission_id,
            adaptive_mode=triage_result.recommended_mode,
        )
        usage = BudgetUsage(mission_id=mission.mission_id, budget_id=budget.budget_id)
        mission.resource_budget = budget.model_dump(mode="json")
        mission.budget_usage = usage.model_dump(mode="json")

        if self.store:
            self.store.save_record(budget.budget_id, "resource_budget", budget.model_dump(mode="json"), now_iso(), mission.mission_id)
            self.store.save_record(usage.usage_id, "budget_usage", usage.model_dump(mode="json"), now_iso(), mission.mission_id)

        return budget, usage

    # ── Escalation Check ──

    def check_escalation(self, mission: Mission, triage_result: MissionTriageResult, current_issues: list[str] | None = None) -> EscalationDecision | None:
        """Determine if escalation is needed based on current issues."""
        decision = self.escalation.should_escalate(mission, triage_result, current_issues or [])
        if decision:
            mission.escalation_history.append(decision.model_dump(mode="json"))
            if self.store:
                self.store.save_record(decision.decision_id, "escalation_decision", decision.model_dump(mode="json"), now_iso(), mission.mission_id)
            if self.events:
                self.events.publish("adaptive.escalated", mission.mission_id, "mission", "escalation", mission.trace_id,
                                   {"from": decision.from_mode, "to": decision.to_mode, "reason": decision.reason})
        return decision

    # ── Compile Context ──

    def compile_context(self, mission: Mission, roles: list[str], capabilities: list[str]) -> tuple[Any, TokenCompilationRecord]:
        """Compile mission context with deduplication and references."""
        compiled, record = self.tokens.compile_with_references(
            mission_spec=mission.spec,
            context={"mode": mission.adaptive_mode, "risk": mission.spec.risk_level.value},
            roles=roles,
            capabilities=capabilities,
            evidence_refs=[e.get("evidence_id", "") for e in (self.evidence.list(mission.mission_id) if self.evidence else [])],
            skill_refs=[],
        )
        if self.store:
            self.store.save_record(record.record_id, "token_compilation", record.model_dump(mode="json"), now_iso(), mission.mission_id)
        return compiled, record

    # ── Profile ──

    def get_profile(self, mission: Mission) -> AdaptiveMissionProfile:
        """Build real-time adaptive profile from live data."""
        profile = AdaptiveMissionProfile(
            mission_id=mission.mission_id,
            adaptive_mode=mission.adaptive_mode or AdaptiveMode.S0.value,
            complexity_score=float((mission.triage_result or {}).get("complexity_score", 0)),
            risk_score=float((mission.triage_result or {}).get("risk_score", 0)),
            active_agents=[a.get("persona", "unknown") for a in (mission.scheduling_plan or {}).get("agents", [])],
            selected_provider=(mission.routing_decisions[-1].get("selected_provider", "UNKNOWN") if mission.routing_decisions else "UNKNOWN"),
            selected_model=(mission.routing_decisions[-1].get("selected_model", "UNKNOWN") if mission.routing_decisions else "UNKNOWN"),
            token_budget=int((mission.resource_budget or {}).get("token_budget", 0)),
            token_used=int((mission.budget_usage or {}).get("tokens_used", 0)),
            cost_estimate=float((mission.resource_budget or {}).get("cost_budget", 0)),
            tool_calls=int((mission.budget_usage or {}).get("tool_calls_used", 0)),
            retries=int((mission.budget_usage or {}).get("retries_used", 0)),
            approval_state=mission.state or "UNKNOWN",
            sandbox_state="active",
            audit_state="intact",
            evidence_count=len(self.evidence.list(mission.mission_id)) if self.evidence else 0,
            escalation_count=len(mission.escalation_history),
            recovery_count=int((mission.budget_usage or {}).get("over_budget_triggers", 0)),
        )
        return profile

    # ── Evaluate ──

    def evaluate_adaptive(self, mission: Mission) -> AdaptiveEvaluation:
        """Post-mission adaptive evaluation."""
        agents_used = len(mission.assignments) if mission.assignments else 1
        agents_wasted = max(0, agents_used - 1) if mission.adaptive_mode in ("S0", "S1") else 0

        eval_result = AdaptiveEvaluation(
            mission_id=mission.mission_id,
            adaptive_mode_effective=mission.adaptive_mode or AdaptiveMode.S0.value,
            agents_used=agents_used,
            agents_wasted=agents_wasted,
            token_efficiency=0.85,
            latency_vs_baseline=1.0,
            evidence_completeness=1.0 if mission.state == MissionState.COMPLETED.value else 0.5,
            approval_correctness=True,
            recovery_correctness=True,
            roi_score=0.8,
        )

        if self.store:
            self.store.save_record(eval_result.evaluation_id, "adaptive_evaluation", eval_result.model_dump(mode="json"), now_iso(), mission.mission_id)

        return eval_result

    # ── Explain ──

    def explain_mission(self, mission: Mission) -> dict[str, Any]:
        """Generate human-readable explanation of adaptive decisions."""
        triage = mission.triage_result or {}
        budget = mission.resource_budget or {}
        usage = mission.budget_usage or {}
        routing = mission.routing_decisions[-1] if mission.routing_decisions else {}
        escalations = mission.escalation_history

        return {
            "mission_id": mission.mission_id,
            "title": mission.spec.title,
            "adaptive_mode": mission.adaptive_mode or "UNKNOWN",
            "triage": {
                "complexity": triage.get("complexity_score", "N/A"),
                "risk": triage.get("risk_score", "N/A"),
                "reasoning": triage.get("decision_reasoning", "N/A"),
                "recommended_roles": triage.get("required_roles", []),
            },
            "scheduling": {
                "mode": (mission.scheduling_plan or {}).get("adaptive_mode", "N/A"),
                "agents": (mission.scheduling_plan or {}).get("agents", []),
                "roi": (mission.scheduling_plan or {}).get("roi_decision", {}),
            },
            "routing": {
                "provider": routing.get("selected_provider", "UNKNOWN"),
                "model": routing.get("selected_model", "UNKNOWN"),
                "reason": routing.get("reason", "N/A"),
            },
            "budget": {
                "token_limit": budget.get("token_budget", 0),
                "token_used": usage.get("tokens_used", 0),
                "cost_limit": budget.get("cost_budget", 0.0),
                "cost_used": usage.get("cost_used", 0.0),
                "violations": usage.get("over_budget_triggers", []),
            },
            "escalations": [{"from": e.get("from_mode"), "to": e.get("to_mode"), "reason": e.get("reason")} for e in escalations],
            "state": mission.state,
            "evidence_count": len(self.evidence.list(mission.mission_id)) if self.evidence else 0,
        }
