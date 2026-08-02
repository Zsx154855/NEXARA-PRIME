"""ResearchIntelligenceEngine — governed research pipeline with source provenance."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ..models import now_iso, new_id
from .cognitive_models import ResearchTask

if TYPE_CHECKING:
    from .memory_controller import MemoryController


class ResearchIntelligenceEngine:
    """Research question → source collection → claim extraction → synthesis → brief.

    All durable writes require evidence_id and are scoped to project_id.
    """

    def __init__(self, memory_controller: MemoryController, project_id: str = "nexara") -> None:
        self._mc = memory_controller
        self._project_id = project_id

    def create_task(self, question: str, scope: str = "", budget: int = 0,
                    time_limit: int = 0) -> ResearchTask:
        return ResearchTask(
            research_id=f"res_{new_id('res')}", question=question, scope=scope,
            budget_limit=budget, time_limit=time_limit,
            source_requirements=["verified"], status="DRAFT",
        )

    def extract_claims(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        claims = []
        for i, src in enumerate(sources):
            claims.append({
                "claim_id": f"claim_{i}", "statement": src.get("content", ""),
                "source": src.get("source", ""), "confidence": 0.5,
                "classification": "INFERENCE",
            })
        return claims

    def map_claims_to_evidence(self, claims: list[dict], evidence: list[dict]) -> list[dict]:
        for claim in claims:
            matches = [e for e in evidence if claim.get("statement", "")[:20] in e.get("summary", "")]
            claim["supporting"] = len(matches)
            claim["evidence_refs"] = [e.get("id", "") for e in matches]
        return claims

    def detect_contradictions(self, claims: list[dict]) -> list[dict]:
        contradictions = []
        for i, c1 in enumerate(claims):
            for c2 in claims[i + 1:]:
                if c1.get("classification") != c2.get("classification"):
                    contradictions.append({"claim_a": c1.get("claim_id"), "claim_b": c2.get("claim_id")})
        return contradictions

    def assess_source_quality(self, sources: list[dict]) -> dict[str, float]:
        scores = {}
        for src in sources:
            name = src.get("source", "unknown")
            conf = src.get("confidence", 0.5)
            scores[name] = conf
        return scores

    def synthesize(self, claims: list[dict]) -> dict[str, Any]:
        return {
            "total_claims": len(claims),
            "average_confidence": sum(c.get("confidence", 0.5) for c in claims) / max(1, len(claims)),
            "top_claims": sorted(claims, key=lambda c: c.get("confidence", 0), reverse=True)[:3],
        }

    def emit_brief(self, task: ResearchTask, claims: list[dict],
                   synthesis: dict, evidence_refs: list[str] | None = None, *,
                   evidence_id: str | None = None, mission_id: str = "global") -> str:
        if not evidence_id:
            raise ValueError("emit_brief requires evidence_id for durable research write")
        content = json.dumps({
            "research_id": task.research_id, "question": task.question,
            "scope": task.scope, "total_claims": len(claims),
            "synthesis": synthesis, "evidence_refs": evidence_refs or [],
            "status": "COMPLETED", "created_at": now_iso(),
            "project_id": self._project_id,
        })
        return self._mc.commit(
            mission_id=mission_id, key=f"research:{self._project_id}:{task.research_id}",
            content=content, kind="procedural", confidence=0.7,
            evidence_id=evidence_id,
        )

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall(self._project_id, layer="procedural")
        key_prefix = f"research:{self._project_id}:"
        research = [r for r in records if r.get("key", "").startswith(key_prefix)]
        return {"total_research_tasks": len(research)}
