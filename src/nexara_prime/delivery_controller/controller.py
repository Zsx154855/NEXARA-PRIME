"""NEXARA Delivery Controller V2 — pre-commit/pre-PR gate automation.

V2 additions: G9_EXTERNAL_REALITY gate, unified Evidence Schema Contract.
Reuses existing Evidence, Governance, and Config modules without modification.
"""

from __future__ import annotations

from .preflight import PreflightRunner
from .gates import GateRunner, GateResult, GateStatus

__all__ = [
    "DeliveryController",
    "ControllerResult",
    "GateRunner",
    "GateResult",
    "GateStatus",
    "PreflightRunner",
]


class ControllerResult:
    """Immutable result of a delivery check run."""

    def __init__(
        self,
        status: str,
        head: str,
        branch: str,
        gates_passed: int,
        gates_total: int,
        failures: list[dict],
        evidence_refs: list[str],
        external_blockers: list[str] | None = None,
        receipt_sha256: str | None = None,
    ) -> None:
        self.status = status
        self.head = head
        self.branch = branch
        self.gates_passed = gates_passed
        self.gates_total = gates_total
        self.failures = failures
        self.evidence_refs = evidence_refs
        self.external_blockers = external_blockers or []
        self.receipt_sha256 = receipt_sha256

    def is_ready(self) -> bool:
        return self.status == "READY_FOR_PR"

    def is_blocked(self) -> bool:
        return self.status in ("BLOCKED", "EXTERNAL_BLOCKED")

    def has_external_blockers(self) -> bool:
        return len(self.external_blockers) > 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "head": self.head,
            "branch": self.branch,
            "gates_passed": self.gates_passed,
            "gates_total": self.gates_total,
            "failures": self.failures,
            "evidence_refs": self.evidence_refs,
            "external_blockers": self.external_blockers,
            "receipt_sha256": self.receipt_sha256,
        }


class DeliveryController:
    """Orchestrates the full delivery gate pipeline (V2: 9 gates)."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        self._preflight = PreflightRunner(repo_root)
        self._gates = GateRunner(repo_root)

    def check(self) -> ControllerResult:
        """Run all 9 gates and return a ControllerResult."""
        head = self._git_head()
        branch = self._git_branch()

        # Run preflight
        env_ok, env_errors = self._preflight.check_environment()
        repo_ok, repo_errors = self._preflight.check_repository()

        if not env_ok:
            return ControllerResult(
                status="BLOCKED", head=head, branch=branch,
                gates_passed=0, gates_total=9,
                failures=[{"gate": "G1_ENVIRONMENT", "errors": env_errors}],
                evidence_refs=[],
            )

        if not repo_ok:
            return ControllerResult(
                status="BLOCKED", head=head, branch=branch,
                gates_passed=0, gates_total=9,
                failures=[{"gate": "G2_REPOSITORY", "errors": repo_errors}],
                evidence_refs=[],
            )

        # Run all 9 gates
        results = self._gates.run_all()
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        failures = [
            {"gate": r.name, "error": r.error, "detail": r.detail}
            for r in results
            if not r.passed
        ]

        # Extract G9 external blockers from evidence
        external_blockers: list[str] = []
        for r in results:
            if r.name == GateStatus.G9_EXTERNAL_REALITY:
                ext = r.evidence.get("external_blockers", [])
                if ext:
                    external_blockers = ext
                break

        # Determine status
        g9_result = None
        for r in results:
            if r.name == GateStatus.G9_EXTERNAL_REALITY:
                g9_result = r
                break

        if failures:
            # Check if ONLY G9 failed (external blocker) and all local gates passed
            local_failures = [f for f in failures if f["gate"] != "G9_EXTERNAL_REALITY"]
            if not local_failures and g9_result and not g9_result.passed:
                status = "EXTERNAL_BLOCKED"
            else:
                status = "BLOCKED"
        elif passed == total:
            status = "READY_FOR_PR"
        else:
            status = "READY_FOR_COMMIT"

        return ControllerResult(
            status=status,
            head=head,
            branch=branch,
            gates_passed=passed,
            gates_total=total,
            failures=failures,
            evidence_refs=[],
            external_blockers=external_blockers,
        )

    def _git_head(self) -> str:
        import subprocess
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=self.repo_root, timeout=10,
            )
            return r.stdout.strip() if r.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _git_branch(self) -> str:
        import subprocess
        try:
            r = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=self.repo_root, timeout=10,
            )
            return r.stdout.strip() if r.returncode == 0 else "unknown"
        except Exception:
            return "unknown"
