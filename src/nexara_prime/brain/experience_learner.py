"""ExperienceLearner — records mission outcomes, extracts patterns, ranks experiences."""

from __future__ import annotations

import json  # noqa: F401
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..models import new_id, now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController


@dataclass
class ExperienceRecord:
    mission_id: str
    outcome: str
    action: str
    result: str
    success: bool
    evidence_id: str
    patterns: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    confidence: float = 0.5
    trace_id: str = ""
    created_at: str = ""


@dataclass
class Pattern:
    pattern_id: str
    pattern_type: str
    description: str
    frequency: int
    success_rate: float
    confidence: float
    examples: list[str] = field(default_factory=list)


class ExperienceLearner:
    """Records mission outcomes, extracts success/failure patterns, ranks experiences."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    def record_outcome(
        self, mission_id: str, outcome: str, action: str, result: str,
        success: bool, evidence_id: str | None = None, trace_id: str = "",
    ) -> str:
        exp = ExperienceRecord(
            mission_id=mission_id, outcome=outcome, action=action,
            result=result, success=success, evidence_id=evidence_id or "",
            trace_id=trace_id, created_at=now_iso(), confidence=0.5,
        )
        return self._mc.commit(
            mission_id=mission_id, key=f"exp:{mission_id}:{new_id('exp')}",
            content=self._serialize_exp(exp), kind="experience",
            evidence_id=evidence_id, confidence=0.5 if success else 0.3,
        )

    def record_lesson(self, mission_id: str, lesson: str, evidence_id: str | None = None) -> str:
        return self._mc.commit(
            mission_id=mission_id, key=f"lesson:{mission_id}:{new_id('lesson')}",
            content=json.dumps({"lesson": lesson, "created_at": now_iso()}),
            kind="procedural", evidence_id=evidence_id, confidence=0.5,
        )

    def extract_patterns(self, limit: int = 50) -> list[Pattern]:
        records = self._mc.rank_retrieve(query="outcome success failure", top_k=limit, layers=["episodic"], min_confidence=0.1)
        action_results: dict[str, list[bool]] = {}
        for r in records:
            if r.get("kind") != "experience":
                continue
            data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
            action = data.get("action", "unknown")
            action_results.setdefault(action, []).append(data.get("success", False))

        patterns: list[Pattern] = []
        for action, results in action_results.items():
            if len(results) < 3:
                continue
            rate = sum(1 for r in results if r) / len(results)
            ptype = "tool_selection_success" if rate > 0.7 else "decision_path_outcome" if rate < 0.3 else "timing_pattern"
            patterns.append(Pattern(
                pattern_id=f"pat_{new_id('pat')}", pattern_type=ptype,
                description=f"Action '{action}': {rate:.0%} success ({len(results)} samples)",
                frequency=len(results), success_rate=rate,
                confidence=min(1.0, len(results) / 10.0),
            ))
        return sorted(patterns, key=lambda p: p.confidence * p.success_rate, reverse=True)

    def rank_experiences(self, keywords: str, top_k: int = 10) -> list[ExperienceRecord]:
        records = self._mc.rank_retrieve(query=keywords, top_k=top_k * 2, layers=["episodic"], min_confidence=0.1)
        exps: list[ExperienceRecord] = []
        for r in records:
            if r.get("kind") == "experience":
                exp = self._deserialize_exp(r)
                if exp:
                    exp.confidence *= 1.0 + (0.1 if exp.success else -0.05)
                    exp.confidence = max(0.1, min(1.0, exp.confidence))
                    exps.append(exp)
        return sorted(exps, key=lambda e: e.confidence * (1.5 if e.success else 0.5), reverse=True)[:top_k]

    def get_lessons(self, query: str = "", top_k: int = 10) -> list[str]:
        records = self._mc.rank_retrieve(query=query or "lesson", top_k=top_k, layers=["procedural"], min_confidence=0.1)
        lessons: list[str] = []
        for r in records:
            if r.get("kind") == "procedural":
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                lessons.append(data.get("lesson", ""))
        return [x for x in lessons if x]

    def prune_irrelevant(self, threshold: float = 0.2) -> int:
        records = self._mc.rank_retrieve(query="experience", top_k=200, layers=["episodic"], min_confidence=0.0)
        return sum(1 for r in records if float(r.get("confidence", 0.5)) < threshold)

    def summarize(self) -> dict[str, Any]:
        patterns = self.extract_patterns(limit=20)
        return {"patterns_found": len(patterns), "top_patterns": [(p.description, p.success_rate) for p in patterns[:5]], "success_actions": len([p for p in patterns if p.success_rate > 0.7]), "failure_actions": len([p for p in patterns if p.success_rate < 0.3])}

    @staticmethod
    def _serialize_exp(exp: ExperienceRecord) -> str:
        return json.dumps({"mission_id": exp.mission_id, "outcome": exp.outcome, "action": exp.action, "result": exp.result, "success": exp.success, "evidence_id": exp.evidence_id, "patterns": exp.patterns, "lessons": exp.lessons, "confidence": exp.confidence, "trace_id": exp.trace_id, "created_at": exp.created_at})

    @staticmethod
    def _deserialize_exp(record: dict) -> ExperienceRecord | None:
        try:
            data = json.loads(record.get("content", "{}")) if isinstance(record.get("content"), str) else record.get("content", {})
            return ExperienceRecord(
                mission_id=data.get("mission_id", ""), outcome=data.get("outcome", ""),
                action=data.get("action", ""), result=data.get("result", ""),
                success=data.get("success", False), evidence_id=data.get("evidence_id", ""),
                patterns=data.get("patterns", []), lessons=data.get("lessons", []),
                confidence=float(data.get("confidence", 0.5)), trace_id=data.get("trace_id", ""),
                created_at=data.get("created_at", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return None
