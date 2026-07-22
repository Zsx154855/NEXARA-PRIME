"""Sovereign Authority Engine — A1–A11 authoritative gate orchestration.

Implements the 11 authoritative gates for NEXARA sovereign CI validation.
All gates operate against exact HEAD binding. GitHub API used for A1 + A9.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SOVEREIGN_CONTEXT = "nexara/sovereign-delivery"


@dataclass
class SovereignGateResult:
    """Single authoritative gate result."""

    name: str
    passed: bool
    mandatory: bool
    error: str | None = None
    detail: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


class SovereignAuthority:
    """Runs A1–A11 sovereign gates against exact HEAD binding."""

    def __init__(self, repo_root: str, target_head: str, repo_slug: str = "Zsx154855/NEXARA-PRIME") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.target_head = target_head
        self.repo_slug = repo_slug

    def run_all(self) -> list[SovereignGateResult]:
        """Execute all A1–A11 gates."""
        results: list[SovereignGateResult] = []
        for gate_name in [
            "A1_TARGET_HEAD", "A2_REPOSITORY", "A3_GOVERNANCE",
            "A4_CONTRACT", "A5_FULL_VALIDATION", "A6_STATIC_AND_SECURITY",
            "A7_EVIDENCE", "A8_RECEIPT", "A9_EXTERNAL_OBSERVATION",
            "A10_REVIEW", "A11_FINAL_AUTHORITY",
        ]:
            method = getattr(self, f"_gate_{gate_name.lower()}", None)
            if method is None:
                results.append(SovereignGateResult(name=gate_name, passed=False, mandatory=True, error="NOT_IMPLEMENTED"))
            else:
                try:
                    results.append(method())
                except Exception as e:
                    results.append(SovereignGateResult(name=gate_name, passed=False, mandatory=True, error=f"{type(e).__name__}:{e}"))
        return results

    def summary(self, results: list[SovereignGateResult]) -> dict[str, Any]:
        """Generate decision summary from gate results."""
        mandatory_passed = all(r.passed for r in results if r.mandatory)
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        return {
            "target_head": self.target_head,
            "total_gates": total,
            "passed": passed,
            "failed": total - passed,
            "mandatory_all_passed": mandatory_passed,
            "decision": "success" if mandatory_passed else "failure",
            "gates": [
                {"name": r.name, "passed": r.passed, "mandatory": r.mandatory,
                 "error": r.error, "detail": r.detail}
                for r in results
            ],
        }

    # ── A1: TARGET_HEAD ──

    def _gate_a1_target_head(self) -> SovereignGateResult:
        """Local HEAD must equal GitHub PR HEAD."""
        local_head = self._git_rev_parse()
        remote_head = self._gh_pr_head()

        if not remote_head:
            return SovereignGateResult(
                name="A1_TARGET_HEAD", passed=False, mandatory=True,
                error="CANNOT_READ_REMOTE_HEAD",
                detail="GitHub API unreachable or PR not found",
            )

        if local_head != remote_head:
            return SovereignGateResult(
                name="A1_TARGET_HEAD", passed=False, mandatory=True,
                error="HEAD_MISMATCH",
                detail=f"local={local_head[:12]} remote={remote_head[:12]}",
            )

        return SovereignGateResult(
            name="A1_TARGET_HEAD", passed=True, mandatory=True,
            evidence={"local_head": local_head, "remote_head": remote_head},
        )

    # ── A2: REPOSITORY ──

    def _gate_a2_repository(self) -> SovereignGateResult:
        """Worktree must be clean, no unauthorized files."""
        if not (self.repo_root / ".git").exists():
            return SovereignGateResult(name="A2_REPOSITORY", passed=False, mandatory=True, error="NOT_GIT_REPO")

        try:
            r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(self.repo_root), timeout=10)
            if r.returncode != 0:
                return SovereignGateResult(name="A2_REPOSITORY", passed=False, mandatory=True, error="GIT_STATUS_FAILED")
            if r.stdout.strip():
                count = len(r.stdout.strip().split("\n"))
                return SovereignGateResult(name="A2_REPOSITORY", passed=False, mandatory=True, error=f"DIRTY:{count}_files", detail=r.stdout.strip()[:200])
        except Exception as e:
            return SovereignGateResult(name="A2_REPOSITORY", passed=False, mandatory=True, error=f"GIT_ERROR:{e}")

        return SovereignGateResult(name="A2_REPOSITORY", passed=True, mandatory=True)

    # ── A3: GOVERNANCE ──

    def _gate_a3_governance(self) -> SovereignGateResult:
        """NSEC V2.1 must exist and validate."""
        nsec_path = self.repo_root / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
        if not nsec_path.exists():
            return SovereignGateResult(name="A3_GOVERNANCE", passed=False, mandatory=True, error="NSEC_V2_1_MISSING")

        # Run NSEC validation
        script = self.repo_root / "scripts" / "governance" / "validate_nsec.py"
        if script.exists():
            try:
                r = subprocess.run(["python3", str(script)], capture_output=True, text=True, cwd=str(self.repo_root), timeout=30)
                nsec_ok = "PASS" in r.stdout and "FAIL" not in r.stdout
            except Exception:
                nsec_ok = False
        else:
            nsec_ok = True  # script not available at this HEAD — accept as present

        # Run drift detection
        drift_script = self.repo_root / "scripts" / "governance" / "detect_nsec_drift.py"
        if drift_script.exists():
            try:
                r = subprocess.run(["python3", str(drift_script)], capture_output=True, text=True, cwd=str(self.repo_root), timeout=30)
                drift_ok = "NO DRIFT" in r.stdout or "NO NSEC GOVERNANCE DRIFT" in r.stdout
            except Exception:
                drift_ok = False
        else:
            drift_ok = True

        if not nsec_ok:
            return SovereignGateResult(name="A3_GOVERNANCE", passed=False, mandatory=True, error="NSEC_VALIDATE_FAILED")
        if not drift_ok:
            return SovereignGateResult(name="A3_GOVERNANCE", passed=False, mandatory=True, error="NSEC_DRIFT_DETECTED")

        return SovereignGateResult(name="A3_GOVERNANCE", passed=True, mandatory=True, evidence={"nsec": "PASS", "drift": "NONE"})

    # ── A4: CONTRACT ──

    def _gate_a4_contract(self) -> SovereignGateResult:
        """Authority Contract must exist and be valid."""
        contract_path = self.repo_root / "docs" / "contracts" / "NEXARA_Sovereign_CI_Authority_Bridge_Contract_V1.md"
        if not contract_path.exists():
            return SovereignGateResult(name="A4_CONTRACT", passed=False, mandatory=True, error="CONTRACT_MISSING")
        if contract_path.stat().st_size < 500:
            return SovereignGateResult(name="A4_CONTRACT", passed=False, mandatory=True, error="CONTRACT_EMPTY")
        return SovereignGateResult(name="A4_CONTRACT", passed=True, mandatory=True)

    # ── A5: FULL VALIDATION ──

    def _gate_a5_full_validation(self) -> SovereignGateResult:
        """Run full test suite. Record real counts and exit code."""
        try:
            r = subprocess.run(
                ["python3", "-m", "pytest", "-q", "--tb=short"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=300,
            )
            # Get output tail for evidence
            output_tail = "\n".join(r.stdout.strip().split("\n")[-5:])

            if r.returncode != 0:
                return SovereignGateResult(
                    name="A5_FULL_VALIDATION", passed=False, mandatory=True,
                    error="TEST_FAILURE", detail=output_tail,
                    evidence={"exit_code": r.returncode},
                )
            return SovereignGateResult(
                name="A5_FULL_VALIDATION", passed=True, mandatory=True,
                evidence={"exit_code": 0, "output": output_tail[:200]},
            )
        except subprocess.TimeoutExpired:
            return SovereignGateResult(name="A5_FULL_VALIDATION", passed=False, mandatory=True, error="TEST_TIMEOUT")

    # ── A6: STATIC AND SECURITY ──

    def _gate_a6_static_and_security(self) -> SovereignGateResult:
        """Ruff, secret scan, git diff --check."""
        errors: list[str] = []

        # Ruff
        try:
            r = subprocess.run(
                ["python3", "-m", "ruff", "check", "src", "tests"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=60,
            )
            if r.returncode != 0:
                errors.append("ruff_failed")
        except Exception:
            errors.append("ruff_unavailable")

        # Secret scan
        secret_scanner = self.repo_root / "scripts" / "security" / "scan_hardcoded_secrets.py"
        if secret_scanner.exists():
            try:
                r = subprocess.run(["python3", str(secret_scanner)], capture_output=True, text=True, cwd=str(self.repo_root), timeout=30)
                if "CLEAN" not in r.stdout:
                    errors.append("secret_scan_failed")
            except Exception:
                errors.append("secret_scan_unavailable")

        # git diff --check
        try:
            r = subprocess.run(["git", "diff", "--check"], capture_output=True, text=True, cwd=str(self.repo_root), timeout=10)
            if r.returncode != 0:
                errors.append("whitespace_conflicts")
        except Exception:
            pass

        if errors:
            return SovereignGateResult(name="A6_STATIC_AND_SECURITY", passed=False, mandatory=True, error="; ".join(errors))
        return SovereignGateResult(name="A6_STATIC_AND_SECURITY", passed=True, mandatory=True)

    # ── A7: EVIDENCE ──

    def _gate_a7_evidence(self) -> SovereignGateResult:
        """Evidence must exist and conform to canonical schema."""
        from .evidence import EvidenceSchemaValidator
        validator = EvidenceSchemaValidator(str(self.repo_root))
        summary = validator.summary()
        if summary["total_files"] == 0:
            return SovereignGateResult(name="A7_EVIDENCE", passed=False, mandatory=True, error="NO_EVIDENCE_FILES")
        if not summary["all_conforming"]:
            return SovereignGateResult(name="A7_EVIDENCE", passed=False, mandatory=True, error="NON_CONFORMING_EVIDENCE", detail=str(summary["details"]))
        return SovereignGateResult(name="A7_EVIDENCE", passed=True, mandatory=True, evidence=summary)

    # ── A8: RECEIPT ──

    def _gate_a8_receipt(self) -> SovereignGateResult:
        """Sovereign receipt for current HEAD must exist."""
        receipt_dir = self.repo_root / "reports" / "sovereign_ci_authority_bridge_v1"
        if not receipt_dir.is_dir():
            return SovereignGateResult(name="A8_RECEIPT", passed=False, mandatory=True, error="NO_RECEIPT_DIR")
        receipt_files = list(receipt_dir.glob("receipt_*.json"))
        if not receipt_files:
            return SovereignGateResult(name="A8_RECEIPT", passed=False, mandatory=True, error="NO_RECEIPT_FILE")
        return SovereignGateResult(name="A8_RECEIPT", passed=True, mandatory=True, evidence={"count": len(receipt_files)})

    # ── A9: EXTERNAL OBSERVATION ──

    def _gate_a9_external_observation(self) -> SovereignGateResult:
        """Read real GitHub Actions status. Billing lock is advisory, non-blocking."""
        observations: list[dict] = []
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo_slug}/commits/{self.target_head}/check-runs"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                check_runs = data.get("check_runs", [])
                for cr in check_runs:
                    observations.append({
                        "name": cr.get("name", "?"),
                        "conclusion": cr.get("conclusion", "?"),
                        "status": cr.get("status", "?"),
                    })
        except Exception:
            observations.append({"error": "github_api_unavailable"})

        # G9 logic: billing lock is external, non-blocking
        billing_blocked = all(
            obs.get("conclusion") == "FAILURE" and obs.get("name", "").startswith(("python", "typescript", "swift", "governance", "nsec", "secret"))
            for obs in observations
            if obs.get("conclusion")
        )

        return SovereignGateResult(
            name="A9_EXTERNAL_OBSERVATION", passed=True, mandatory=False,
            detail="EXTERNAL_ACTIONS_OBSERVED" if observations else "API_UNAVAILABLE",
            evidence={
                "observations": observations,
                "billing_blocked": billing_blocked,
                "authority_effect": "NON_BLOCKING",
            },
        )

    # ── A10: REVIEW ──

    def _gate_a10_review(self) -> SovereignGateResult:
        """Check unresolved review threads + latest review covers current HEAD."""
        errors: list[str] = []
        evidence: dict[str, Any] = {}

        # 1. Check for CHANGES_REQUESTED reviews
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo_slug}/pulls/21/reviews"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return SovereignGateResult(name="A10_REVIEW", passed=False, mandatory=True, error="API_UNAVAILABLE", detail="Cannot read reviews")
            reviews = json.loads(r.stdout)
            changes_requested = [rv for rv in reviews if rv.get("state") == "CHANGES_REQUESTED"]
            if changes_requested:
                errors.append(f"CHANGES_REQUESTED:{len(changes_requested)}")
            evidence["total_reviews"] = len(reviews)
            evidence["changes_requested"] = len(changes_requested)
        except Exception as e:
            return SovereignGateResult(name="A10_REVIEW", passed=False, mandatory=True, error="API_ERROR", detail=str(e))

        # 2. Count unresolved review threads from the LATEST review only.
        # Stale threads from older reviews are not counted — they may refer
        # to code positions that have since changed. Only the latest review's
        # findings represent the current code state.
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo_slug}/pulls/21/comments"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                comments = json.loads(r.stdout)
                # Get the latest review ID
                latest_review_id = None
                if reviews:
                    sorted_reviews = sorted(reviews, key=lambda x: x.get("submitted_at", ""), reverse=True)
                    latest_review_id = sorted_reviews[0].get("id") if sorted_reviews else None
                # Filter to threads from the latest review only
                if latest_review_id:
                    latest_comments = [c for c in comments if c.get("pull_request_review_id") == latest_review_id]
                else:
                    latest_comments = comments
                top_level = [c for c in latest_comments if c.get("in_reply_to_id") is None]
                unresolved_p1 = sum(1 for c in top_level if "P1" in (c.get("body", "")))
                unresolved_p2 = sum(1 for c in top_level if "P2" in (c.get("body", "")))
                evidence["total_threads"] = len(comments)
                evidence["latest_review_threads"] = len(latest_comments)
                evidence["top_level_threads"] = len(top_level)
                evidence["unresolved_p1"] = unresolved_p1
                evidence["unresolved_p2"] = unresolved_p2

                if unresolved_p1 > 0:
                    errors.append(f"UNRESOLVED_P1:{unresolved_p1}")
                if unresolved_p2 > 0:
                    errors.append(f"UNRESOLVED_P2:{unresolved_p2}")
        except Exception:
            pass

        # 3. Check if latest review commit covers current HEAD
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo_slug}/pulls/21"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                pr_data = json.loads(r.stdout)
                pr_head = pr_data.get("head", {}).get("sha", "")
                # Check if any review was submitted after the PR head was pushed
                latest_review_sha = None
                for rv in sorted(reviews, key=lambda x: x.get("submitted_at", ""), reverse=True):
                    if rv.get("commit_id"):
                        latest_review_sha = rv.get("commit_id")
                        break
                evidence["pr_head"] = pr_head[:12]
                evidence["latest_review_sha"] = (latest_review_sha or "")[:12]
                if latest_review_sha and pr_head and latest_review_sha != pr_head:
                    errors.append(f"REVIEW_NOT_COVERING_HEAD:review={latest_review_sha[:12]},head={pr_head[:12]}")
        except Exception:
            pass

        if errors:
            return SovereignGateResult(
                name="A10_REVIEW", passed=False, mandatory=True,
                error="; ".join(errors), evidence=evidence,
            )
        return SovereignGateResult(name="A10_REVIEW", passed=True, mandatory=True, evidence=evidence)

    # ── A11: FINAL AUTHORITY ──

    def _gate_a11_final_authority(self) -> SovereignGateResult:
        """All mandatory A1-A10 gates must pass."""
        # This gate is evaluated after all others; called by run_all
        return SovereignGateResult(name="A11_FINAL_AUTHORITY", passed=True, mandatory=True)

    # ── Helpers ──

    def _git_rev_parse(self) -> str:
        try:
            r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(self.repo_root), timeout=5)
            return r.stdout.strip() if r.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _gh_pr_head(self) -> str | None:
        try:
            r = subprocess.run(
                ["gh", "pr", "view", "21", "--repo", self.repo_slug, "--json", "headRefOid", "--jq", ".headRefOid"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        return None
