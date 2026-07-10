from __future__ import annotations

from .models import CompiledPrompt, MissionSpec, new_id


class TokenCompiler:
    """Compiles bounded object references instead of sending the whole workspace."""

    def compile(self, spec: MissionSpec, skill_refs: list[str], object_refs: list[str], evidence_refs: list[str], context_summary: str = "") -> CompiledPrompt:
        objective = spec.objective.strip()
        if len(objective) > 900:
            objective = objective[:900] + "…"
        task = (
            f"Mission {spec.mission_id}: {objective}\n"
            f"Boundaries: {'; '.join(spec.boundaries) or 'bounded local workspace'}\n"
            f"Acceptance: {'; '.join(spec.acceptance_criteria) or 'produce verifiable evidence'}\n"
            f"Context: {context_summary[:500]}"
        )
        system = "NEXARA PRIME worker. Follow the WorkContract, use only mounted capabilities, emit evidence, and stop on policy conflict."
        estimate = max(1, int((len(system) + len(task) + sum(map(len, skill_refs + object_refs + evidence_refs))) / 4))
        return CompiledPrompt(
            prompt_id=new_id("prompt"), mission_id=spec.mission_id, system=system, task=task,
            skill_refs=skill_refs, object_refs=object_refs, evidence_refs=evidence_refs, estimated_tokens=estimate,
        )
