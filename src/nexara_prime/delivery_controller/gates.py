"""Gate runner: executes all 8 delivery gates and returns results."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GateResult:
    """Single gate execution result."""

    name: str
    passed: bool
    error: str | None = None
    detail: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


class GateStatus:
    """Gate name constants."""

    G1_ENVIRONMENT = "G1_ENVIRONMENT"
    G2_REPOSITORY = "G2_REPOSITORY"
    G3_CONTRACT = "G3_CONTRACT"
    G4_TEST = "G4_TEST"
    G5_EVIDENCE = "G5_EVIDENCE"
    G6_RECEIPT = "G6_RECEIPT"
    G7_CI_DEPENDENCY = "G7_CI_DEPENDENCY"
    G8_REVIEW_READINESS = "G8_REVIEW_READINESS"
    G9_EXTERNAL_REALITY = "G9_EXTERNAL_REALITY"

    ALL = [
        G1_ENVIRONMENT, G2_REPOSITORY, G3_CONTRACT, G4_TEST,
        G5_EVIDENCE, G6_RECEIPT, G7_CI_DEPENDENCY, G8_REVIEW_READINESS,
        G9_EXTERNAL_REALITY,
    ]


class GateRunner:
    """Executes all defined delivery gates against a repo."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root).resolve()

    def run_all(self) -> list[GateResult]:
        """Run all 8 gates and return results."""
        results: list[GateResult] = []
        for gate_name in GateStatus.ALL:
            method = getattr(self, f"_gate_{gate_name.lower()}", None)
            if method is None:
                results.append(GateResult(
                    name=gate_name, passed=False,
                    error="GATE_NOT_IMPLEMENTED",
                    detail=f"No handler for {gate_name}",
                ))
            else:
                try:
                    result = method()
                    results.append(result)
                except Exception as e:
                    results.append(GateResult(
                        name=gate_name, passed=False,
                        error="GATE_EXCEPTION",
                        detail=f"{type(e).__name__}: {e}",
                    ))
        return results

    # ── G1: Environment ──

    def _gate_g1_environment(self) -> GateResult:
        import sys
        errors: list[str] = []

        if sys.version_info < (3, 9):
            errors.append(f"python<3.9:{sys.version}")
        try:
            import pydantic  # noqa: F401
        except ImportError:
            errors.append("no_pydantic")
        try:
            import pytest  # noqa: F401
        except ImportError:
            errors.append("no_pytest")

        if errors:
            return GateResult(
                name=GateStatus.G1_ENVIRONMENT, passed=False,
                error="ENV_FAIL", detail="; ".join(errors),
            )
        return GateResult(name=GateStatus.G1_ENVIRONMENT, passed=True)

    # ── G2: Repository ──

    def _gate_g2_repository(self) -> GateResult:
        errors: list[str] = []

        if not (self.repo_root / ".git").exists():
            return GateResult(
                name=GateStatus.G2_REPOSITORY, passed=False,
                error="NOT_GIT_REPO",
            )

        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=10,
            )
            if r.returncode != 0:
                errors.append(f"git_status_rc={r.returncode}")
            elif r.stdout.strip():
                count = len(r.stdout.strip().split("\n"))
                errors.append(f"dirty:{count}_files")
        except Exception as e:
            errors.append(f"git_fail:{e}")

        # Check main branch guard
        try:
            r = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip() == "main":
                errors.append("on_main_branch")
        except Exception:
            pass

        if errors:
            return GateResult(
                name=GateStatus.G2_REPOSITORY, passed=False,
                error="REPO_FAIL", detail="; ".join(errors),
            )
        return GateResult(name=GateStatus.G2_REPOSITORY, passed=True)

    # ── G3: Contract ──

    def _gate_g3_contract(self) -> GateResult:
        nsec_path = self.repo_root / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
        authority_path = self.repo_root / "governance" / "authority_index.yaml"
        merge_path = self.repo_root / "governance" / "contracts" / "MERGE_CONTRACT_V1.yaml"

        errors: list[str] = []
        for label, p in [
            ("nsec_v2", nsec_path),
            ("authority_index", authority_path),
            ("merge_contract", merge_path),
        ]:
            if not p.exists():
                errors.append(f"missing_{label}")
            elif p.stat().st_size == 0:
                errors.append(f"empty_{label}")

        if errors:
            return GateResult(
                name=GateStatus.G3_CONTRACT, passed=False,
                error="CONTRACT_MISSING", detail="; ".join(errors),
            )
        return GateResult(name=GateStatus.G3_CONTRACT, passed=True)

    # ── G4: Test ──

    def _gate_g4_test(self) -> GateResult:
        try:
            r = subprocess.run(
                ["python3", "-m", "pytest", "-q", "--tb=short", "-x"],
                capture_output=True, text=True,
                cwd=str(self.repo_root), timeout=120,
            )
            if r.returncode != 0:
                last_lines = "\n".join(r.stdout.strip().split("\n")[-5:]) or r.stderr.strip()[-300:]
                return GateResult(
                    name=GateStatus.G4_TEST, passed=False,
                    error="TEST_FAIL", detail=last_lines,
                )
        except subprocess.TimeoutExpired:
            return GateResult(
                name=GateStatus.G4_TEST, passed=False,
                error="TEST_TIMEOUT",
            )
        except FileNotFoundError:
            return GateResult(
                name=GateStatus.G4_TEST, passed=False,
                error="PYTEST_NOT_FOUND",
            )
        except Exception as e:
            return GateResult(
                name=GateStatus.G4_TEST, passed=False,
                error="TEST_EXCEPTION", detail=str(e),
            )
        return GateResult(name=GateStatus.G4_TEST, passed=True)

    # ── G5: Evidence (V2: schema contract enforcement) ──

    def _gate_g5_evidence(self) -> GateResult:
        from .evidence import EvidenceSchemaValidator
        evidence_dir = self.repo_root / ".nexara" / "evidence"
        if not evidence_dir.exists() or not evidence_dir.is_dir():
            return GateResult(
                name=GateStatus.G5_EVIDENCE, passed=False,
                error="NO_EVIDENCE_DIR",
            )

        json_files = list(evidence_dir.glob("*.json"))
        if not json_files:
            return GateResult(
                name=GateStatus.G5_EVIDENCE, passed=False,
                error="NO_EVIDENCE_FILES",
            )

        validator = EvidenceSchemaValidator(str(self.repo_root))
        schema_summary = validator.summary()

        errors: list[str] = []
        warnings: list[str] = []

        for detail in schema_summary.get("details", []):
            if detail["status"] == "INVALID":
                errors.append(f"invalid_schema:{detail['file']}")
            elif detail["status"] == "LEGACY":
                warnings.append(f"legacy_schema:{detail['file']}")

        if errors:
            return GateResult(
                name=GateStatus.G5_EVIDENCE, passed=False,
                error="EVIDENCE_INVALID",
                detail="; ".join(errors),
                evidence={"count": len(json_files), "schema": schema_summary},
            )

        # Warnings for legacy files (non-blocking)
        detail_msg = ""
        if warnings:
            detail_msg = "LEGACY_MIGRATION_NEEDED: " + "; ".join(warnings)

        return GateResult(
            name=GateStatus.G5_EVIDENCE, passed=len(errors) == 0,
            error=None if not errors else "EVIDENCE_INVALID",
            detail=detail_msg if detail_msg else None,
            evidence={"count": len(json_files), "schema": schema_summary},
        )

    # ── G6: Receipt ──

    def _gate_g6_receipt(self) -> GateResult:
        receipt_dir = self.repo_root / "reports"
        if not receipt_dir.exists():
            return GateResult(
                name=GateStatus.G6_RECEIPT, passed=False,
                error="NO_REPORTS_DIR",
            )

        receipt_files = list(receipt_dir.rglob("*receipt*.md")) + list(receipt_dir.rglob("*receipt*.json"))
        if not receipt_files:
            return GateResult(
                name=GateStatus.G6_RECEIPT, passed=False,
                error="NO_RECEIPT_FILES",
                detail="Receipt missing but evidence gate passed",
            )

        # Check at least one receipt is valid
        valid = False
        for f in receipt_files:
            try:
                content = f.read_text()
                if len(content) > 20:
                    valid = True
                    break
            except OSError:
                pass

        if not valid:
            return GateResult(
                name=GateStatus.G6_RECEIPT, passed=False,
                error="RECEIPT_EMPTY",
            )
        return GateResult(
            name=GateStatus.G6_RECEIPT, passed=True,
            evidence={"receipt_count": len(receipt_files)},
        )

    # ── G7: CI Dependency ──

    def _gate_g7_ci_dependency(self) -> GateResult:
        ci_scripts = [
            self.repo_root / "scripts" / "ci" / "validate_merge_contract.py",
            self.repo_root / "scripts" / "security" / "scan_hardcoded_secrets.py",
            self.repo_root / "scripts" / "governance" / "validate_nsec.py",
            self.repo_root / "scripts" / "governance" / "detect_nsec_drift.py",
        ]
        ruff_config = self.repo_root / "ruff.toml"
        pyproject = self.repo_root / "pyproject.toml"

        missing = [str(p.relative_to(self.repo_root)) for p in ci_scripts if not p.exists()]
        if not ruff_config.exists() and not pyproject.exists():
            missing.append("ruff.toml or pyproject.toml")

        if missing:
            return GateResult(
                name=GateStatus.G7_CI_DEPENDENCY, passed=False,
                error="CI_DEPS_MISSING", detail="; ".join(missing),
            )
        return GateResult(name=GateStatus.G7_CI_DEPENDENCY, passed=True)

    # ── G8: Review Readiness ──

    def _gate_g8_review_readiness(self) -> GateResult:
        errors: list[str] = []

        # Check for merge conflicts
        try:
            r = subprocess.run(
                ["git", "diff", "--check"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=10,
            )
            if r.returncode != 0:
                errors.append("whitespace_conflicts:" + r.stderr.strip()[:100])
        except Exception:
            pass

        # Check for TODO/FIXME without tracking
        try:
            r = subprocess.run(
                ["git", "diff", "HEAD", "--", "*.py"],
                capture_output=True, text=True, cwd=str(self.repo_root), timeout=15,
            )
            if r.returncode == 0:
                diff = r.stdout
                if "TODO" in diff or "FIXME" in diff:
                    errors.append("unresolved_todos_in_diff")
        except Exception:
            pass

        if errors:
            return GateResult(
                name=GateStatus.G8_REVIEW_READINESS, passed=False,
                error="REVIEW_BLOCKED", detail="; ".join(errors),
            )
        return GateResult(name=GateStatus.G8_REVIEW_READINESS, passed=True)

    # ── G9: External Reality ──

    def _gate_g9_external_reality(self) -> GateResult:
        """Detect external blockers: GitHub Actions billing, unprovisioned CI, documented blockers."""
        findings: list[str] = []
        external_blockers: list[str] = []
        local_authoritative = False

        # Check AGENTS.md for documented external blockers
        agents_md = self.repo_root / "AGENTS.md"
        if agents_md.exists():
            try:
                content = agents_md.read_text().lower()
                if "billing lock" in content:
                    external_blockers.append("GITHUB_ACTIONS_BILLING_LOCK")
                if "local sovereign verification as primary" in content or \
                   "local verification is authoritative" in content:
                    local_authoritative = True
                    findings.append("local_verification_authoritative")
            except OSError:
                findings.append("cannot_read_agents_md")

        # Check RECEIPT.json for known CI status
        receipt_files = list(self.repo_root.rglob("RECEIPT.json"))
        for rf in receipt_files[:5]:  # limit to 5 to avoid scanning entire repo
            try:
                data = json.loads(rf.read_text())
                ci_status = data.get("verification_governance", {}).get("ci_status", "")
                ci_reason = data.get("verification_governance", {}).get("ci_block_reason", "")
                if ci_status == "NOT_EXECUTED_EXTERNAL_BLOCK":
                    if ci_reason and ci_reason not in external_blockers:
                        external_blockers.append(ci_reason)
                    findings.append(f"receipt_confirms_external_block:{rf.parent.name}")
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # Check CI workflows for runs-on directives requiring external runners
        workflows_dir = self.repo_root / ".github" / "workflows"
        if workflows_dir.is_dir():
            for wf in workflows_dir.glob("*.yml"):
                try:
                    content = wf.read_text()
                    if "runs-on:" in content:
                        findings.append(f"ci_workflow_found:{wf.name}")
                        # Extract runs-on targets
                        for line in content.split("\n"):
                            if "runs-on:" in line:
                                target = line.split("runs-on:")[-1].strip()
                                findings.append(f"ci_target:{target}")
                except OSError:
                    pass

        # Decision
        if not external_blockers:
            return GateResult(
                name=GateStatus.G9_EXTERNAL_REALITY, passed=True,
                evidence={"findings": findings, "external_blockers": []},
            )

        if local_authoritative:
            # External blockers exist but local verification is authoritative
            return GateResult(
                name=GateStatus.G9_EXTERNAL_REALITY, passed=True,
                detail=f"EXTERNAL_BLOCKERS_EXIST_BUT_LOCAL_AUTHORITATIVE: {'; '.join(external_blockers)}",
                evidence={
                    "findings": findings,
                    "external_blockers": external_blockers,
                    "local_authoritative": True,
                },
            )

        # External blockers exist and no local-authoritative override
        return GateResult(
            name=GateStatus.G9_EXTERNAL_REALITY, passed=False,
            error="EXTERNAL_BLOCKERS_UNACKNOWLEDGED",
            detail=f"Blockers: {'; '.join(external_blockers)}. No local-authoritative override found in AGENTS.md.",
            evidence={
                "findings": findings,
                "external_blockers": external_blockers,
                "local_authoritative": False,
            },
        )
