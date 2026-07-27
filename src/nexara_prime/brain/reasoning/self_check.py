"""SelfCheckValidator — 5 automated verification checks on reasoning chains.

Runs before presenting conclusions. Catches contradictions, missing steps,
overconfident inferences, and circular reasoning.
"""

from __future__ import annotations

from .models import ReasoningStep, SelfCheckResult


class SelfCheckValidator:
    """Verifies reasoning correctness with 5 checks."""

    name = "self_check_validator"

    def validate(self, steps: list[ReasoningStep]) -> SelfCheckResult:
        """Run all 5 checks. Return SelfCheckResult with pass/fail details."""
        checks = [
            self._check_consistency(steps),
            self._check_completeness(steps),
            self._check_evidence_coverage(steps),
            self._check_calibration(steps),
            self._check_circularity(steps),
        ]

        passed = sum(1 for c in checks if c["passed"])
        failures = [c for c in checks if not c["passed"]]
        remediation = [c["remediation"] for c in failures if c.get("remediation")]

        return SelfCheckResult(
            overall_pass=len(failures) == 0,
            checks_passed=passed,
            checks_total=len(checks),
            failures=failures,
            remediation=remediation,
        )

    def _check_consistency(self, steps: list[ReasoningStep]) -> dict:
        """Check that no two INFER/SYNTHESIZE steps produce contradictory conclusions."""
        conclusions = [
            (s.step_id, s.output.lower())
            for s in steps
            if s.step_type in ("INFER", "SYNTHESIZE") and s.output
        ]
        contradictions = []
        opposites = {
            "yes": "no", "no": "yes",
            "true": "false", "false": "true",
            "pass": "fail", "fail": "pass",
            "success": "failure", "failure": "success",
        }
        for i, (id_a, out_a) in enumerate(conclusions):
            for id_b, out_b in conclusions[i + 1:]:
                if out_b in opposites and opposites[out_b] in out_a:
                    contradictions.append({"step_a": id_a, "step_b": id_b, "a": out_a, "b": out_b})

        return {
            "check": "consistency",
            "passed": len(contradictions) == 0,
            "detail": f"{len(contradictions)} contradictions found",
            "remediation": "Re-reason conflicting steps" if contradictions else "",
        }

    def _check_completeness(self, steps: list[ReasoningStep]) -> dict:
        """Verify all step dependencies are satisfied."""
        step_ids = {s.step_id for s in steps}
        orphans = []
        for s in steps:
            for dep in s.depends_on:
                if dep not in step_ids:
                    orphans.append({"step": s.step_id, "missing_dep": dep})

        return {
            "check": "completeness",
            "passed": len(orphans) == 0,
            "detail": f"{len(orphans)} orphan dependencies",
            "remediation": "Add missing dependent steps" if orphans else "",
        }

    def _check_evidence_coverage(self, steps: list[ReasoningStep]) -> dict:
        """Verify all INFER and SYNTHESIZE steps have at least 1 evidence reference."""
        uncovered = [
            s.step_id for s in steps
            if s.step_type in ("INFER", "SYNTHESIZE") and len(s.evidence_refs) == 0
        ]
        return {
            "check": "evidence_coverage",
            "passed": len(uncovered) == 0,
            "detail": f"{len(uncovered)} steps without evidence",
            "remediation": "Add evidence references to uncovered steps" if uncovered else "",
        }

    def _check_calibration(self, steps: list[ReasoningStep]) -> dict:
        """Flag INFER/SYNTHESIZE steps where confidence > evidence_strength + 0.3 (overconfident)."""
        overconfident = []
        for s in steps:
            if s.step_type not in ("INFER", "SYNTHESIZE"):
                continue
            evidence_count = len(s.evidence_refs)
            evidence_strength = min(1.0, evidence_count / 5.0)
            if s.confidence > evidence_strength + 0.3:
                overconfident.append({
                    "step": s.step_id,
                    "confidence": s.confidence,
                    "evidence_strength": round(evidence_strength, 2),
                })

        return {
            "check": "calibration",
            "passed": len(overconfident) == 0,
            "detail": f"{len(overconfident)} overconfident steps",
            "remediation": "Lower confidence or add evidence for overconfident steps" if overconfident else "",
        }

    def _check_circularity(self, steps: list[ReasoningStep]) -> dict:
        """Detect cycles in step dependency graph using DFS."""
        graph: dict[str, list[str]] = {s.step_id: s.depends_on for s in steps}
        cycles = []

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in graph}

        def dfs(node: str, path: list[str]) -> bool:
            color[node] = GRAY
            path.append(node)
            for neighbor in graph.get(node, []):
                if color.get(neighbor) == GRAY:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True
                if color.get(neighbor) == WHITE:
                    if dfs(neighbor, path):
                        return True
            path.pop()
            color[node] = BLACK
            return False

        for node in graph:
            if color.get(node) == WHITE:
                dfs(node, [])

        return {
            "check": "circularity",
            "passed": len(cycles) == 0,
            "detail": f"{len(cycles)} cycles detected",
            "remediation": "Break circular dependencies in reasoning chain" if cycles else "",
        }
