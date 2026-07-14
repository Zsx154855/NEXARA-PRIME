"""Benchmark Runner — executes baseline/candidate comparison for evolution."""
from __future__ import annotations

from dataclasses import dataclass

from .db import SQLiteStore
from .events import EventBus
from .models import Mission, new_id, now_iso
from .product_reality.models import BenchmarkResult, ImprovementProposal


@dataclass
class _MetricSet:
    correctness: float
    reliability: float
    safety: float
    evidence_coverage: float
    token_efficiency: float
    recovery_rate: float

    def to_dict(self) -> dict:
        return {
            "correctness": self.correctness,
            "reliability": self.reliability,
            "safety": self.safety,
            "evidence_coverage": self.evidence_coverage,
            "token_efficiency": self.token_efficiency,
            "recovery_rate": self.recovery_rate,
        }

    @staticmethod
    def from_mission(mission: Mission) -> _MetricSet:
        evidence_count = len(mission.result.get("evidence_refs", []))
        tool_count = mission.result.get("tool_count", 0)
        tokens = mission.result.get("total_tokens", 1000)
        has_report = bool(mission.result.get("report_path"))
        return _MetricSet(
            correctness=1.0 if has_report and mission.state.value in {"EVALUATION", "COMPLETED"} else 0.5,
            reliability=1.0 if tool_count > 0 and evidence_count > 0 else 0.4,
            safety=1.0 if mission.spec.risk_level.value in {"R0", "R1", "R2"} else 0.3,
            evidence_coverage=min(1.0, evidence_count / 4),
            token_efficiency=min(1.0, 500 / max(500, tokens)),
            recovery_rate=1.0 if mission.rollback_point else 0.3,
        )


class BenchmarkRunner:
    """Runs baseline vs candidate benchmarks for improvement proposals.

    Per Blueprint §16: Observe → Diagnose → Candidate → Simulation →
    Benchmark → Approval → Deploy → Monitor → Rollback.
    """

    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def run(
        self,
        proposal: ImprovementProposal,
        baseline_mission: Mission,
        candidate_mission: Mission,
    ) -> BenchmarkResult:
        baseline = _MetricSet.from_mission(baseline_mission)
        candidate = _MetricSet.from_mission(candidate_mission)

        metrics = ["correctness", "reliability", "safety", "evidence_coverage", "token_efficiency", "recovery_rate"]
        baseline_d = baseline.to_dict()
        candidate_d = candidate.to_dict()

        improvements: dict[str, float] = {}
        regressions: list[str] = []
        for m in metrics:
            delta = candidate_d[m] - baseline_d[m]
            improvements[m] = round(delta, 4)
            if delta < -0.1:
                regressions.append(f"{m}_regression: {baseline_d[m]:.2f}→{candidate_d[m]:.2f}")

        avg_baseline = sum(baseline_d[m] for m in metrics) / len(metrics)
        avg_candidate = sum(candidate_d[m] for m in metrics) / len(metrics)
        improvement_pct = round(((avg_candidate - avg_baseline) / max(0.01, avg_baseline)) * 100, 2)

        passed = len(regressions) == 0 and improvement_pct >= 0

        result = BenchmarkResult(
            proposal_id=proposal.proposal_id,
            mission_id=proposal.mission_id,
            baseline_score=baseline_d,
            candidate_score=candidate_d,
            improvement_pct=improvement_pct,
            regression_flags=regressions,
            passed=passed,
            evidence_refs=proposal.evidence_refs,
        )
        self.store.save_record(result.benchmark_id, "benchmark", result.model_dump(mode="json"), result.created_at, proposal.mission_id)
        self.events.publish("benchmark.completed", proposal.mission_id, "mission", "benchmark_runner", baseline_mission.trace_id, result.model_dump(mode="json"))
        return result

    def compare_candidates(
        self,
        proposal: ImprovementProposal,
        candidates: list[BenchmarkResult],
    ) -> BenchmarkResult | None:
        """Select the best candidate from multiple benchmark results."""
        if not candidates:
            return None
        best = max(candidates, key=lambda r: r.improvement_pct)
        return best

    def reject_with_evidence(
        self,
        proposal: ImprovementProposal,
        result: BenchmarkResult,
    ) -> dict:
        """Reject a proposal with benchmark evidence."""
        rejection = {
            "proposal_id": proposal.proposal_id,
            "verdict": "rejected",
            "benchmark_id": result.benchmark_id,
            "regression_flags": result.regression_flags,
            "improvement_pct": result.improvement_pct,
            "reason": "regression_detected" if result.regression_flags else "insufficient_improvement",
            "requires": result.regression_flags or ["improvement_pct < threshold"],
        }
        self.events.publish("proposal.rejected", proposal.mission_id, "mission", "benchmark_runner", "", rejection)
        return rejection
