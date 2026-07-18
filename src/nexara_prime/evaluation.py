from __future__ import annotations

from .db import SQLiteStore
from .events import EventBus
from .models import EvaluationResult, Mission, MissionState


class EvaluationEngine:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def evaluate(self, mission: Mission, evidence_count: int, tool_count: int, input_tokens: int, output_tokens: int, *, idempotency_key: str | None = None) -> EvaluationResult:
        if idempotency_key:
            existing = self.store.find_record("evaluation", "idempotency_key", idempotency_key)
            if existing:
                # Strip idempotency_key from stored payload before model_validate
                existing_payload = {k: v for k, v in existing.items() if k != "idempotency_key"}
                return EvaluationResult.model_validate(existing_payload)
        has_report = bool(mission.result.get("report_path"))
        evidence_coverage = 1.0 if evidence_count >= 4 else min(1.0, evidence_count / 4)
        correctness = 1.0 if has_report and mission.state in {MissionState.EVALUATION.value, MissionState.COMPLETED.value} else 0.5
        reliability = 1.0 if tool_count > 0 and evidence_count > 0 else 0.5
        safety = 1.0 if mission.spec.risk_level.value in {"R0", "R1", "R2"} else 0.0
        token_efficiency = min(1.0, 500 / max(500, input_tokens + output_tokens))
        cost_score = 1.0 if input_tokens + output_tokens < 5_000 else 0.8
        recovery_rate = 1.0 if mission.rollback_point else 0.5
        passed = all(value >= 0.9 for value in (correctness, reliability, safety, evidence_coverage))
        result = EvaluationResult(
            mission_id=mission.mission_id, correctness=correctness, reliability=reliability, safety=safety,
            evidence_coverage=evidence_coverage, token_efficiency=token_efficiency, cost_score=cost_score,
            recovery_rate=recovery_rate, passed=passed,
            notes=["Deterministic MVP evaluation; replace with domain evaluators per mission type."],
        )
        self.store.save_record(result.evaluation_id, "evaluation", {**result.model_dump(mode="json"), "idempotency_key": idempotency_key}, result.created_at, mission.mission_id)
        self.events.publish("mission.evaluated", mission.mission_id, "mission", "evaluation_engine", mission.trace_id, result.model_dump(mode="json"))
        return result

    def list(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("evaluation", mission_id)
