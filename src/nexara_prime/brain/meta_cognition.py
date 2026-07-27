"""MetaCognitionController — knows what it knows, detects gaps, calibrates confidence."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso, new_id
from .cognitive_models import CognitiveAssessment

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class MetaCognitionController:
    """Self-awareness: knowns, unknowns, calibration, overconfidence detection, safe stop."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def assess_knowledge_state(self, mission_id: str, context: dict[str, Any] | None = None) -> CognitiveAssessment:
        ctx = context or {}
        known = ctx.get("known_facts", [])
        evidence = ctx.get("evidence", [])
        assumptions = ctx.get("assumptions", [])

        gaps = [f"Missing evidence for: {a}" for a in assumptions if not any(a in str(e) for e in evidence)]
        unknowns = ctx.get("unknowns", [])
        contradictions = self._count_contradictions(known)

        confidence = 0.7 if len(evidence) >= 3 else 0.4 if evidence else 0.2
        overconfident = confidence > 0.6 and not evidence
        escalation = overconfident or len(gaps) > 2

        return CognitiveAssessment(
            assessment_id=f"ca_{new_id('ca')}",
            mission_id=mission_id,
            known_facts=known,
            unknowns=unknowns + gaps,
            assumptions=assumptions,
            evidence_gaps=gaps,
            confidence=confidence,
            contradiction_count=contradictions,
            calibration_score=1.0 - min(1.0, len(gaps) * 0.2),
            recommended_action="escalate" if escalation else "proceed",
            human_escalation_required=escalation,
            created_at=now_iso(),
        )

    def identify_unknowns(self, known: list[str], required: list[str]) -> list[str]:
        return [r for r in required if r not in known]

    def validate_assumptions(self, assumptions: list[str], evidence: list[str]) -> list[dict[str, Any]]:
        results = []
        for a in assumptions:
            supported = any(a.lower() in e.lower() for e in evidence)
            results.append({"assumption": a, "validated": supported, "risk": "high" if not supported else "low"})
        return results

    def detect_overconfidence(self, assessment: CognitiveAssessment) -> bool:
        return assessment.confidence > 0.6 and len(assessment.evidence_gaps) > 1

    def calibrate_confidence(self, assessment: CognitiveAssessment, evidence_count: int,
                             assumption_count: int, contradiction_count: int) -> float:
        base = min(1.0, evidence_count * 0.2)
        penalty = assumption_count * 0.1 + contradiction_count * 0.15
        return max(0.1, base - penalty)

    def require_escalation(self, assessment: CognitiveAssessment) -> bool:
        return assessment.human_escalation_required or assessment.contradiction_count > 2

    def require_research(self, assessment: CognitiveAssessment) -> bool:
        return len(assessment.evidence_gaps) > 0 or len(assessment.unknowns) > 2

    def stop_unsafe(self, assessment: CognitiveAssessment) -> bool:
        return assessment.contradiction_count > 3 or self.detect_overconfidence(assessment)

    def record_assessment(self, assessment: CognitiveAssessment) -> str:
        content = json.dumps({
            "assessment_id": assessment.assessment_id, "mission_id": assessment.mission_id,
            "known_facts": assessment.known_facts, "unknowns": assessment.unknowns,
            "evidence_gaps": assessment.evidence_gaps, "confidence": assessment.confidence,
            "calibration_score": assessment.calibration_score,
            "escalation_required": assessment.human_escalation_required,
            "created_at": assessment.created_at,
        })
        return self._mc.commit(
            mission_id=assessment.mission_id, key=f"cognitive:{assessment.assessment_id}",
            content=content, kind="procedural", confidence=assessment.confidence,
        )

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="procedural")
        assessments = [r for r in records if r.get("key", "").startswith("cognitive:")]
        return {"total_assessments": len(assessments)}

    @staticmethod
    def _count_contradictions(facts: list[str]) -> int:
        return 0  # simplified — production would compare pairs
