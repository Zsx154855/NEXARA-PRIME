from __future__ import annotations

from .capabilities import CapabilityRegistry
from .models import AgentAssignment, MissionSpec, Persona, RuntimeRole


PERSONA_BY_ROLE = {
    RuntimeRole.ORCHESTRATOR: Persona.HERMES,
    RuntimeRole.PLANNER: Persona.SOLACE,
    RuntimeRole.ANALYST: Persona.NYX,
    RuntimeRole.RESEARCHER: Persona.ORION,
    RuntimeRole.EXECUTOR: Persona.VERTEX,
    RuntimeRole.REVIEWER: Persona.LUMEN,
    RuntimeRole.AUDITOR: Persona.ATLAS,
    RuntimeRole.ARCHIVIST: Persona.ECHO,
}


class AdaptiveScheduler:
    """Creates only the runtime roles required by the mission."""

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def schedule(self, spec: MissionSpec) -> list[AgentAssignment]:
        text = f"{spec.objective} {' '.join(spec.deliverables)}".lower()
        roles = [RuntimeRole.ORCHESTRATOR, RuntimeRole.PLANNER, RuntimeRole.EXECUTOR, RuntimeRole.REVIEWER, RuntimeRole.AUDITOR, RuntimeRole.ARCHIVIST]
        if any(word in text for word in ("analy", "data", "metric", "report")):
            roles.insert(2, RuntimeRole.ANALYST)
        if spec.source_dir or any(word in text for word in ("research", "read", "资料", "source", "document")):
            roles.insert(2, RuntimeRole.RESEARCHER)
        roles = list(dict.fromkeys(roles))
        assignments: list[AgentAssignment] = []
        for role in roles:
            persona = PERSONA_BY_ROLE[role]
            required = ["skill.evidence", "policy.risk", "model.mock"]
            if role == RuntimeRole.RESEARCHER:
                required += ["tool.file_read"]
            if role == RuntimeRole.EXECUTOR:
                required += ["tool.file_write_report", "tool.code_exec"]
            if role == RuntimeRole.ARCHIVIST:
                required += ["memory.sqlite"]
            assignment = AgentAssignment(mission_id=spec.mission_id, persona=persona, runtime_role=role)
            assignment.loaded_capabilities = self.registry.mount_for(assignment.assignment_id, required)
            assignments.append(assignment)
        return assignments

    def release(self, assignments: list[AgentAssignment]) -> None:
        for assignment in assignments:
            self.registry.unmount_for(assignment.assignment_id)
