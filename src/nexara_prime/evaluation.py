from __future__ import annotations

import hashlib

from .db import SQLiteStore
from .events import EventBus
from .models import EvaluationResult, Mission, MissionState


class EvaluationEngine:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def evaluate(self, mission: Mission, evidence_count: int, tool_count: int, input_tokens: int, output_tokens: int, *, idempotency_key: str | None = None) -> EvaluationResult:
        if idempotency_key:
            existing_envelope = self.store.find_record_envelope(
                "evaluation_idempotency", "idempotency_key", idempotency_key
            )
            existing = (
                existing_envelope["payload"] if existing_envelope else None
            )
            if (
                existing_envelope
                and existing_envelope.get("mission_id") == mission.mission_id
                and existing
                and existing.get("evaluation_id")
            ):
                record_envelope = self.store.get_record_envelope(
                    existing["evaluation_id"]
                )
                record = record_envelope["payload"] if record_envelope else None
                if record:
                    result = EvaluationResult.model_validate(record)
                    if (
                        result.mission_id != mission.mission_id
                        or result.idempotency_key not in {None, idempotency_key}
                    ):
                        raise ValueError("evaluation_idempotency_conflict")
                    self._publish_evaluation(mission, result, idempotency_key)
                    return result
        has_report = bool(mission.result.get("report_path"))
        evidence_coverage = 1.0 if evidence_count >= 4 else min(1.0, evidence_count / 4)
        correctness = 1.0 if has_report and mission.state in {MissionState.EVALUATION.value, MissionState.COMPLETED.value} else 0.5
        reliability = 1.0 if tool_count > 0 and evidence_count > 0 else 0.5
        safety = 1.0 if mission.spec.risk_level.value in {"R0", "R1", "R2"} else 0.0
        token_efficiency = min(1.0, 500 / max(500, input_tokens + output_tokens))
        cost_score = 1.0 if input_tokens + output_tokens < 5_000 else 0.8
        recovery_rate = 1.0 if mission.rollback_point else 0.5
        passed = all(value >= 0.9 for value in (correctness, reliability, safety, evidence_coverage))
        digest = (
            hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
            if idempotency_key
            else None
        )
        identity = {"evaluation_id": f"eval_{digest}"} if digest else {}
        result = EvaluationResult(
            **identity,
            mission_id=mission.mission_id, correctness=correctness, reliability=reliability, safety=safety,
            evidence_coverage=evidence_coverage, token_efficiency=token_efficiency, cost_score=cost_score,
            recovery_rate=recovery_rate, passed=passed,
            notes=["Deterministic MVP evaluation; replace with domain evaluators per mission type."],
            idempotency_key=idempotency_key,
        )
        if idempotency_key:
            try:
                self.store.save_records_atomically(
                    [
                        {
                            "record_id": result.evaluation_id,
                            "record_type": "evaluation",
                            "payload": result.model_dump(mode="json"),
                            "created_at": result.created_at,
                            "mission_id": mission.mission_id,
                        },
                        {
                            "record_id": f"evidem_{digest}",
                            "record_type": "evaluation_idempotency",
                            "payload": {
                                "idempotency_key": idempotency_key,
                                "evaluation_id": result.evaluation_id,
                            },
                            "created_at": result.created_at,
                            "mission_id": mission.mission_id,
                        },
                    ]
                )
            except ValueError as exc:
                if str(exc) != "atomic_record_identity_conflict":
                    raise
                winner_envelope = self.store.find_record_envelope(
                    "evaluation_idempotency",
                    "idempotency_key",
                    idempotency_key,
                )
                winner = winner_envelope["payload"] if winner_envelope else None
                winner_record_envelope = (
                    self.store.get_record_envelope(winner["evaluation_id"])
                    if (
                        winner_envelope
                        and winner_envelope.get("mission_id") == mission.mission_id
                        and winner
                        and winner.get("evaluation_id")
                    )
                    else None
                )
                winner_record = (
                    winner_record_envelope["payload"]
                    if winner_record_envelope
                    else None
                )
                if not winner_record:
                    raise
                result = EvaluationResult.model_validate(winner_record)
                if (
                    result.mission_id != mission.mission_id
                    or result.idempotency_key != idempotency_key
                ):
                    raise ValueError("evaluation_idempotency_conflict") from exc
        else:
            self.store.save_record(
                result.evaluation_id,
                "evaluation",
                result.model_dump(mode="json"),
                result.created_at,
                mission.mission_id,
            )
        self._publish_evaluation(mission, result, idempotency_key)
        return result

    def _publish_evaluation(
        self,
        mission: Mission,
        result: EvaluationResult,
        idempotency_key: str | None,
    ) -> None:
        self.events.publish(
            "mission.evaluated",
            mission.mission_id,
            "mission",
            "evaluation_engine",
            mission.trace_id,
            result.model_dump(mode="json"),
            idempotency_key=(
                f"evaluation-event:{idempotency_key}" if idempotency_key else None
            ),
        )

    def list(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("evaluation", mission_id)
