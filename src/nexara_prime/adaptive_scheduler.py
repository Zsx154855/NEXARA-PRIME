from __future__ import annotations

from typing import Any

from .models import (
    AdaptiveMode,
    CapabilityScore,
    MissionSpec,
    MissionTriageResult,
    Persona,
    RuntimeRole,
    SchedulingPlan,
    SchedulerPolicyVersion,
    new_id,
    now_iso,
)


PERSONA_BY_ROLE: dict[RuntimeRole, Persona] = {
    RuntimeRole.ORCHESTRATOR: Persona.NEXARA,
    RuntimeRole.PLANNER: Persona.SOLACE,
    RuntimeRole.ANALYST: Persona.NYX,
    RuntimeRole.RESEARCHER: Persona.ORION,
    RuntimeRole.EXECUTOR: Persona.VERTEX,
    RuntimeRole.REVIEWER: Persona.LUMEN,
    RuntimeRole.AUDITOR: Persona.ATLAS,
    RuntimeRole.ARCHIVIST: Persona.ECHO,
}


class AdaptiveMultiAgentScheduler:
    """Adaptive multi-agent scheduler with ROI-gated agent allocation.

    Implements role lifecycle (create, assign, pause, merge, replace, retire)
    and dynamic scaling driven by mission complexity, risk, and ROI scoring.
    """

    def __init__(
        self,
        policy: SchedulerPolicyVersion | None = None,
    ) -> None:
        self.policy = policy or SchedulerPolicyVersion()
        self._active_agents: dict[str, dict[str, Any]] = {}  # agent_id -> agent info
        self._agent_counter: int = 0

    # ── Role Lifecycle ──────────────────────────────────────────────

    def create_role(
        self,
        role: RuntimeRole,
        persona: Persona,
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new agent role descriptor and return it."""
        agent_id = new_id("agent")
        entry: dict[str, Any] = {
            "agent_id": agent_id,
            "role": role.value if hasattr(role, "value") else str(role),
            "persona": persona.value if hasattr(persona, "value") else str(persona),
            "status": "created",
            "capabilities": capabilities or [],
            "created_at": now_iso(),
        }
        self._active_agents[agent_id] = entry
        self._agent_counter += 1
        return entry

    def assign_role(
        self,
        agent_id: str,
        mission_id: str,
        step_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Assign an existing agent to a mission step."""
        agent = self._active_agents.get(agent_id)
        if agent is None:
            return None
        agent["status"] = "assigned"
        agent["mission_id"] = mission_id
        agent["current_step_id"] = step_id
        agent["assigned_at"] = now_iso()
        return agent

    def pause_role(self, agent_id: str) -> dict[str, Any] | None:
        """Pause an active agent."""
        agent = self._active_agents.get(agent_id)
        if agent is None:
            return None
        agent["status"] = "paused"
        agent["paused_at"] = now_iso()
        return agent

    def merge_roles(
        self,
        primary_id: str,
        secondary_id: str,
    ) -> dict[str, Any] | None:
        """Merge secondary agent's capabilities into primary, retire secondary."""
        primary = self._active_agents.get(primary_id)
        secondary = self._active_agents.get(secondary_id)
        if primary is None or secondary is None:
            return None
        merged_caps = list(
            set(primary.get("capabilities", []))
            | set(secondary.get("capabilities", []))
        )
        primary["capabilities"] = merged_caps
        primary["merged_at"] = now_iso()
        primary["merged_from"] = secondary_id
        self._retire_role(secondary_id)
        return primary

    def replace_role(
        self,
        old_agent_id: str,
        new_role: RuntimeRole,
        new_persona: Persona,
        capabilities: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Replace an agent with a new one of a different role/persona."""
        old = self._active_agents.get(old_agent_id)
        if old is None:
            return None
        self._retire_role(old_agent_id)
        caps = capabilities or old.get("capabilities", [])
        return self.create_role(new_role, new_persona, caps)

    def retire_role(self, agent_id: str) -> bool:
        """Public API to retire an agent."""
        return self._retire_role(agent_id)

    def _retire_role(self, agent_id: str) -> bool:
        agent = self._active_agents.get(agent_id)
        if agent is None:
            return False
        agent["status"] = "retired"
        agent["retired_at"] = now_iso()
        return True

    # ── ROI Gate ────────────────────────────────────────────────────

    def _compute_roi_score(
        self,
        quality_gain: float,
        token_increase: float,
        latency_increase: float,
        parallelism_possible: bool,
        failure_cost: float,
        verification_needed: bool,
        coupling: float,
    ) -> float:
        """Compute ROI score for adding an agent.

        roi_score = (quality_gain - (token_increase*0.01 + latency_increase*0.001 + coupling_penalty))
                     / max(failure_cost*0.1, 1)

        coupling_penalty = coupling * 0.05
        If verification_needed, add a small bonus.
        If parallelism_possible, add a bonus for scalability.
        """
        coupling_penalty = coupling * 0.05
        numerator = (
            quality_gain
            - (token_increase * 0.01)
            - (latency_increase * 0.001)
            - coupling_penalty
        )
        if verification_needed:
            numerator += 0.1
        if parallelism_possible:
            numerator += 0.15
        denominator = max(failure_cost * 0.1, 1.0)
        return numerator / denominator

    # ── Schedule ────────────────────────────────────────────────────

    def schedule(
        self,
        mission_spec: MissionSpec,
        triage_result: MissionTriageResult,
        capabilities: list[CapabilityScore],
    ) -> SchedulingPlan:
        """Produce a scheduling plan based on mission spec and triage result.

        Applies ROI gate logic and adaptive mode constraints:
        - S0/S1: start with 1 agent, add reviewer only if verification_needed.
        - S2: moderate parallelism, ROI-gated additions.
        - S3: governed mode, up to 8 agents, dual verification.
        """
        adaptive_mode = AdaptiveMode(triage_result.recommended_mode)
        max_agents = self.policy.max_agents_default
        if adaptive_mode == AdaptiveMode.S3:
            max_agents = self.policy.max_agents_governed

        roi_threshold = self.policy.roi_threshold

        # ── Determine initial agent set ──
        agents: list[dict[str, Any]] = []
        task_dag: dict[str, Any] = {}
        parallelism_degree = 1

        # Always start with orchestrator + executor
        base_roles: list[RuntimeRole] = [
            RuntimeRole.ORCHESTRATOR,
            RuntimeRole.EXECUTOR,
        ]

        # S0 / S1: single-agent preferred
        if adaptive_mode in (AdaptiveMode.S0, AdaptiveMode.S1):
            base_roles = [RuntimeRole.ORCHESTRATOR]
            if triage_result.required_evidence_level in (
                "detailed",
                "comprehensive",
            ):
                base_roles.append(RuntimeRole.EXECUTOR)

        # Add planner for complex missions
        if triage_result.complexity_score > 0.4:
            base_roles.append(RuntimeRole.PLANNER)

        # Add analyst for data-heavy missions
        if triage_result.data_sensitivity in ("medium", "high"):
            base_roles.append(RuntimeRole.ANALYST)

        # Add researcher when research needed
        if triage_result.required_evidence_level in ("detailed", "comprehensive"):
            if RuntimeRole.RESEARCHER not in base_roles:
                base_roles.append(RuntimeRole.RESEARCHER)

        # Single agent verification: if S0/S1 and verification needed, add reviewer
        needs_reviewer = (
            triage_result.required_evidence_level in ("detailed", "comprehensive")
            or triage_result.risk_score > 0.5
        )
        if needs_reviewer and adaptive_mode in (AdaptiveMode.S0, AdaptiveMode.S1):
            base_roles.append(RuntimeRole.REVIEWER)

        # De-duplicate roles while preserving order
        seen: set[str] = set()
        ordered_roles: list[RuntimeRole] = []
        for r in base_roles:
            k = r.value if hasattr(r, "value") else str(r)
            if k not in seen:
                seen.add(k)
                ordered_roles.append(r)

        # Create agents for each base role
        for role in ordered_roles:
            persona = PERSONA_BY_ROLE.get(role, Persona.NEXARA)
            agent_caps = self._select_capabilities(role, capabilities)
            agent = self.create_role(role, persona, [c.capability_id for c in agent_caps])
            agents.append(agent)

        # ── Dynamic scaling: evaluate ROI for additional agents ──
        remaining_roles = [
            r
            for r in RuntimeRole
            if r not in ordered_roles
            and r != RuntimeRole.ARCHIVIST  # add archivist last
        ]
        # Add archivist only if evidence level is comprehensive
        if triage_result.required_evidence_level == "comprehensive":
            remaining_roles.append(RuntimeRole.ARCHIVIST)

        for role in remaining_roles:
            if len(agents) >= max_agents:
                break

            if role == RuntimeRole.REVIEWER and needs_reviewer:
                pass  # always add reviewer when needed (already handled above for S0/S1)

            # Compute expected ROI for adding this role
            quality_gain = self._estimate_quality_gain(role, triage_result)
            token_increase = self._estimate_token_increase(role)
            latency_increase = self._estimate_latency_increase(role)
            parallelism_possible = adaptive_mode in (AdaptiveMode.S2, AdaptiveMode.S3)
            failure_cost = triage_result.risk_score * 10.0
            verification_needed = needs_reviewer
            coupling = self._estimate_coupling(role, ordered_roles)

            roi = self._compute_roi_score(
                quality_gain=quality_gain,
                token_increase=token_increase,
                latency_increase=latency_increase,
                parallelism_possible=parallelism_possible,
                failure_cost=failure_cost,
                verification_needed=verification_needed,
                coupling=coupling,
            )

            if roi >= roi_threshold:
                persona = PERSONA_BY_ROLE.get(role, Persona.NEXARA)
                agent_caps = self._select_capabilities(role, capabilities)
                agent = self.create_role(
                    role, persona, [c.capability_id for c in agent_caps]
                )
                agents.append(agent)

        # ── S3 requires dual verification ──
        if adaptive_mode == AdaptiveMode.S3:
            reviewer_count = sum(
                1
                for a in agents
                if a["role"] == RuntimeRole.REVIEWER.value
            )
            if reviewer_count < 2:
                for _ in range(2 - reviewer_count):
                    if len(agents) >= max_agents:
                        break
                    persona = PERSONA_BY_ROLE.get(RuntimeRole.REVIEWER, Persona.LUMEN)
                    agent_caps = self._select_capabilities(
                        RuntimeRole.REVIEWER, capabilities
                    )
                    agent = self.create_role(
                        RuntimeRole.REVIEWER,
                        persona,
                        [c.capability_id for c in agent_caps],
                    )
                    agents.append(agent)

        # ── Compute DAG and parallelism ──
        task_dag = self._build_task_dag(agents, triage_result)
        parallelism_degree = min(len(agents), triage_result.complexity_score > 0.5 and 3 or 2)

        # ── Duration estimate ──
        estimated_duration_ms = int(
            triage_result.expected_duration_ms / max(parallelism_degree, 1)
        )

        # ── ROI decision record ──
        roi_decision: dict[str, Any] = {
            "policy_version": self.policy.version,
            "adaptive_mode": adaptive_mode.value,
            "max_agents": max_agents,
            "agents_created": len(agents),
            "roi_threshold": roi_threshold,
            "quality_gain_estimate": sum(
                self._estimate_quality_gain(
                    RuntimeRole(a["role"]) if isinstance(a["role"], str) else a["role"],
                    triage_result,
                )
                for a in agents
            ),
        }

        plan = SchedulingPlan(
            plan_id=new_id("schedplan"),
            mission_id=mission_spec.mission_id,
            adaptive_mode=adaptive_mode.value,
            agents=agents,
            task_dag=task_dag,
            parallelism_degree=parallelism_degree,
            estimated_duration_ms=estimated_duration_ms,
            roi_decision=roi_decision,
        )
        return plan

    # ── Internal helpers ────────────────────────────────────────────

    def _select_capabilities(
        self,
        role: RuntimeRole,
        capabilities: list[CapabilityScore],
    ) -> list[CapabilityScore]:
        """Select capabilities matching the role's task types."""
        role_str = role.value if hasattr(role, "value") else str(role)
        matching: list[CapabilityScore] = []
        for cap in capabilities:
            task_types = cap.supported_task_types
            if any(role_str.lower() in tt.lower() for tt in task_types):
                matching.append(cap)
        # Fall back to generic tool/policy capabilities
        if not matching:
            matching = [
                c
                for c in capabilities
                if any(
                    kw in c.capability_id
                    for kw in ("tool", "policy", "skill.core")
                )
            ][:3]
        return matching

    def _estimate_quality_gain(
        self,
        role: RuntimeRole,
        triage_result: MissionTriageResult,
    ) -> float:
        """Estimate quality gain from adding this role (0.0–1.0)."""
        role_str = role.value if hasattr(role, "value") else str(role)
        gains: dict[str, float] = {
            "Orchestrator": 0.5,
            "Planner": 0.4 if triage_result.complexity_score > 0.5 else 0.2,
            "Analyst": 0.35 if triage_result.data_sensitivity == "high" else 0.15,
            "Researcher": 0.4 if triage_result.required_evidence_level == "comprehensive" else 0.2,
            "Executor": 0.3,
            "Reviewer": 0.3 if triage_result.risk_score > 0.5 else 0.1,
            "Auditor": 0.25,
            "Archivist": 0.1,
        }
        return gains.get(role_str, 0.1)

    def _estimate_token_increase(self, role: RuntimeRole) -> float:
        """Estimate token increase from adding this role (in thousands)."""
        role_str = role.value if hasattr(role, "value") else str(role)
        increases: dict[str, float] = {
            "Orchestrator": 8.0,
            "Planner": 6.0,
            "Analyst": 5.0,
            "Researcher": 7.0,
            "Executor": 4.0,
            "Reviewer": 3.0,
            "Auditor": 4.0,
            "Archivist": 2.0,
        }
        return increases.get(role_str, 3.0)

    def _estimate_latency_increase(self, role: RuntimeRole) -> float:
        """Estimate latency increase from adding this role (ms)."""
        role_str = role.value if hasattr(role, "value") else str(role)
        increases: dict[str, float] = {
            "Orchestrator": 200.0,
            "Planner": 300.0,
            "Analyst": 250.0,
            "Researcher": 400.0,
            "Executor": 150.0,
            "Reviewer": 100.0,
            "Auditor": 120.0,
            "Archivist": 80.0,
        }
        return increases.get(role_str, 100.0)

    def _estimate_coupling(
        self,
        role: RuntimeRole,
        existing_roles: list[RuntimeRole],
    ) -> float:
        """Estimate coupling between this role and existing roles (0.0–1.0)."""
        role_str = role.value if hasattr(role, "value") else str(role)
        # Coupling is higher for roles that need to communicate a lot
        high_coupling: dict[str, list[str]] = {
            "Reviewer": ["Executor", "Orchestrator"],
            "Auditor": ["Reviewer", "Executor"],
            "Planner": ["Orchestrator", "Executor"],
        }
        coupling: float = 0.1
        existing_strs = {
            r.value if hasattr(r, "value") else str(r) for r in existing_roles
        }
        for partner in high_coupling.get(role_str, []):
            if partner in existing_strs:
                coupling += 0.3
        return min(coupling, 1.0)

    def _build_task_dag(
        self,
        agents: list[dict[str, Any]],
        triage_result: MissionTriageResult,
    ) -> dict[str, Any]:
        """Build a DAG of task dependencies."""
        dag: dict[str, Any] = {"nodes": [], "edges": []}
        for agent in agents:
            dag["nodes"].append(
                {
                    "agent_id": agent["agent_id"],
                    "role": agent["role"],
                }
            )
        # Simple sequential dependency by default
        for i in range(len(agents) - 1):
            dag["edges"].append(
                {
                    "from": agents[i]["agent_id"],
                    "to": agents[i + 1]["agent_id"],
                    "type": "sequential",
                }
            )
        return dag

    # ── Status ──────────────────────────────────────────────────────

    def active_agent_count(self) -> int:
        """Return the number of currently active (non-retired) agents."""
        return sum(
            1
            for a in self._active_agents.values()
            if a.get("status") != "retired"
        )

    def list_active_agents(self) -> list[dict[str, Any]]:
        """Return all active agent descriptors."""
        return [
            a
            for a in self._active_agents.values()
            if a.get("status") != "retired"
        ]

    def release_all(self) -> None:
        """Retire all active agents."""
        for agent_id in list(self._active_agents.keys()):
            self._retire_role(agent_id)
