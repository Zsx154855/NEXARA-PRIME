"""Opt-in bridge: canonical Runtime evidence -> trusted experience -> next-task choice.

This is a P2 integration experiment, not a default Runtime behavior change:
- BrainDB shares the Runtime's canonical SQLiteStore (no second authority).
- Tool receipts produced by ToolRuntime are converted into admitted experiences.
- A bounded next-objective selector uses only verified experience.

Production auto-wiring remains a product decision (ADR-008); this module is the
smallest verifiable integration and must be explicitly attached by a caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .brain.db import BrainDB
from .brain.experience_assembly import build_trusted_experience_learner
from .brain.experience_learner import ExperienceLearner
from .brain.memory_controller import MemoryController

if TYPE_CHECKING:
    from .runtime import NexaraRuntime


@dataclass
class RuntimeExperienceBridge:
    runtime: NexaraRuntime
    brain: BrainDB
    controller: MemoryController
    learner: ExperienceLearner
    rejected_receipts: int = 0
    already_retired: int = 0


def build_runtime_bridge(runtime: NexaraRuntime) -> RuntimeExperienceBridge:
    """Attach brain memory to the Runtime store; never create a second SQLite file."""
    brain = BrainDB(store=runtime.store)
    controller = MemoryController(db=brain)
    learner = build_trusted_experience_learner(controller, runtime.evidence)
    return RuntimeExperienceBridge(
        runtime=runtime, brain=brain, controller=controller, learner=learner
    )


def _result_summary(invocation: dict[str, Any], limit: int = 500) -> str:
    try:
        text = json.dumps(invocation.get("result", {}), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = "{}"
    return text[:limit]


def capture_mission(bridge: RuntimeExperienceBridge, mission_id: str) -> list[str]:
    """Record one admitted experience per tool receipt; idempotent on replay."""
    created: list[str] = []
    for invocation in bridge.runtime.tools.list_invocations(mission_id):
        evidence_id = invocation.get("receipt_evidence_id")
        if not evidence_id:
            continue
        status = str(invocation.get("status", ""))
        success = status == "completed"
        try:
            memory_id = bridge.learner.record_outcome(
                mission_id,
                "success" if success else "failure",
                str(invocation.get("tool_name", "")),
                _result_summary(invocation),
                success,
                evidence_id=str(evidence_id),
            )
            if _is_archived(bridge, memory_id):
                bridge.already_retired += 1
            else:
                created.append(memory_id)
        except ValueError:
            # One bad receipt must not abort capture of the remaining verified
            # receipts; it is counted for observability and skipped fail-closed.
            bridge.rejected_receipts += 1
    return created


def _is_archived(bridge: RuntimeExperienceBridge, memory_id: str) -> bool:
    return any(
        row.get("memory_id") == memory_id
        for row in bridge.brain.recall(status="archived")
    )


def retire_mission(
    bridge: RuntimeExperienceBridge,
    mission_id: str,
    *,
    reason: str = "",
    actor: str = "operator",
) -> int:
    """Archive captured experiences/lessons and emit a durable audit event."""
    def _audit(payload: dict[str, Any]) -> None:
        bridge.runtime.events.publish(
            "experience.retired",
            mission_id,
            "mission",
            actor,
            f"retire:{mission_id}",
            payload,
            idempotency_key=(
                f"experience-retired:{mission_id}:{payload.get('retired', 0)}"
            ),
        )

    return bridge.learner.retire_experiences(
        mission_id=mission_id, reason=reason, actor=actor, audit=_audit
    )


def close_bridge(bridge: RuntimeExperienceBridge) -> None:
    """Detach semantically only; the Runtime owns the shared connection."""
    # Deliberately does not call brain.close(): it would close runtime.store.
    return None


def select_objective(
    bridge: RuntimeExperienceBridge,
    candidates: list[str],
) -> dict[str, Any]:
    """Choose the candidate with the strongest verified experience support.

    Ties keep the caller's candidate order on purpose: the caller owns priority,
    and select_objective must not invent a hidden secondary ranking. The chosen
    decision is returned unchanged so its evidence can be audited.
    """
    best: tuple[str, float, dict[str, Any]] | None = None
    for objective in candidates:
        decision = bridge.learner.recommend_action(objective)
        if decision.get("action") is None:
            continue
        score = float(decision.get("confidence", 0.0))
        if best is None or score > best[1]:
            best = (objective, score, decision)
    if best is None:
        return {
            "objective": candidates[0] if candidates else "",
            "score": 0.0,
            "decision": None,
            "reason": "no_reliable_experience",
        }
    return {"objective": best[0], "score": best[1], "decision": best[2]}


def experience_count(bridge: RuntimeExperienceBridge, mission_id: str | None = None) -> int:
    rows = bridge.brain.recall(mission_id=mission_id, kind="experience")
    return len(rows)
