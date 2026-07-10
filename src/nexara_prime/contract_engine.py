from __future__ import annotations

from .models import MissionSpec, WorkContract, now_iso


class ContractEngine:
    def create(self, spec: MissionSpec) -> WorkContract:
        return WorkContract(
            mission_id=spec.mission_id,
            objective=spec.objective,
            boundaries=spec.boundaries,
            constraints=spec.constraints,
            deliverables=spec.deliverables,
            acceptance_criteria=spec.acceptance_criteria,
            risk_level=spec.risk_level,
            status="validated",
        )

    def revise(self, contract: WorkContract, change: str) -> WorkContract:
        return contract.model_copy(update={"version": contract.version + 1, "status": "draft", "change_log": [*contract.change_log, f"{now_iso()} {change}"]})

    def approve(self, contract: WorkContract) -> WorkContract:
        return contract.model_copy(update={"status": "approved", "approved_at": now_iso()})
