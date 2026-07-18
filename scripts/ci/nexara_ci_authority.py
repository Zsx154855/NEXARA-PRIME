#!/usr/bin/env python3
"""NEXARA Local CI Authority — evidence-driven, verifiable, dual-track.

Mirrors the formal GitHub Actions ci.yml contract. Produces cryptographically
verifiable receipts. Does NOT claim GitHub required-check status.

Usage:
  python3 scripts/ci/nexara_ci_authority.py --full --evidence
  python3 scripts/ci/nexara_ci_authority.py --full --evidence --head <sha> --precommit
  python3 scripts/ci/nexara_ci_authority.py --check python_tests
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
RUNTIME_DIR = REPO_ROOT / ".runtime" / "ci"
RUNS_DIR = RUNTIME_DIR / "runs"
LOG_DIR_NAME = "logs"
RECEIPT_DIR_NAME = "receipts"
ATTEST_DIR_NAME = "attestations"

SCHEMA_VERSION = "1.0.0"
AUTHORITY_VERSION = "v1.0.0"
EVIDENCE_CLASS = "LOCAL_AUTHORITY_EVIDENCE_ONLY"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short_hash = subprocess.run(
        ["git", "rev-parse", "--short=8", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.strip()
    nonce = secrets.token_hex(4)
    return f"{ts}-{short_hash}-{nonce}"


def run_command(cmd: list[str], cwd: Path, timeout: int = 300,
                env: dict | None = None) -> dict:
    """Run a command safely. Returns structured result dict."""
    started = time.monotonic()
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update({k: str(v) for k, v in env.items()})
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=cmd_env,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"TIMEOUT after {timeout}s"
    except Exception as e:
        exit_code = -2
        stdout = ""
        stderr = str(e)
    elapsed = time.monotonic() - started
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": round(elapsed, 3),
        "timeout_seconds": timeout,
    }


def redact(s: str) -> str:
    """Remove hostname and home dir paths from output."""
    import re
    home = os.path.expanduser("~")
    s = s.replace(home, "$HOME")
    s = re.sub(r'/[Uu]sers/[^/\s]+', '/Users/<redacted>', s)
    s = re.sub(r'(?i)(api_key|token|secret|password|key)=[^\s]+',
               r'\1=<REDACTED>', s)
    return s


class CheckResult:
    def __init__(self, check_id: str, name: str, command: str, cwd: str,
                 applicability: str = "APPLICABLE",
                 applicability_reason: str = ""):
        self.check_id = check_id
        self.name = name
        self.command_redacted = command
        self.cwd = cwd
        self.applicability = applicability
        self.applicability_reason = applicability_reason
        self.started_at = ""
        self.completed_at = ""
        self.duration_seconds = 0.0
        self.exit_code = 0
        self.status = "PENDING"
        self.log_path = ""
        self.log_sha256 = ""
        self.stderr_present = False
        self.timeout_seconds = 0
        self.tool_versions: dict[str, str] = {}
        self.limitations: list[str] = []

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "command_redacted": self.command_redacted,
            "cwd": self.cwd,
            "applicability": self.applicability,
            "applicability_reason": self.applicability_reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "status": self.status,
            "log_path": self.log_path,
            "log_sha256": self.log_sha256,
            "stderr_present": self.stderr_present,
            "timeout_seconds": self.timeout_seconds,
            "tool_versions": self.tool_versions,
            "limitations": self.limitations,
        }


class NexaraCiAuthority:
    """Local CI authority implementing the formal ci.yml contract."""

    def __init__(self, head: str = "", precommit: bool = False,
                 fail_fast: bool = False):
        self.head = head or self._current_head()
        self.remote_head = self._remote_head()
        self.precommit = precommit
        self.fail_fast = fail_fast
        self.run = run_id()
        self.run_dir = RUNS_DIR / self.run
        self.log_dir = self.run_dir / LOG_DIR_NAME
        self.receipt_dir = self.run_dir / RECEIPT_DIR_NAME
        self.attest_dir = self.run_dir / ATTEST_DIR_NAME
        self.checks: list[CheckResult] = []
        self.started_at = now_iso()
        self._create_dirs()

    def _current_head(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=REPO_ROOT, timeout=10,
        ).stdout.strip()

    def _remote_head(self) -> str:
        try:
            return subprocess.run(
                ["git", "ls-remote", "origin",
                 "refs/heads/work/nexara-continuous-integration-train-v1"],
                capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
            ).stdout.strip().split()[0]
        except Exception:
            return "unknown"

    def _create_dirs(self):
        for d in [self.run_dir, self.log_dir, self.receipt_dir, self.attest_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _check_branch(self) -> str:
        return subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True,
            cwd=REPO_ROOT, timeout=10,
        ).stdout.strip()

    def _is_worktree_clean(self) -> bool:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
            cwd=REPO_ROOT, timeout=10,
        )
        return result.stdout.strip() == ""

    def _tool_version(self, cmd: list[str]) -> str:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return (r.stdout + r.stderr).strip().split("\n")[0][:80]
        except Exception:
            return "unknown"

    def execute_check(self, check: CheckResult, cmd: list[str],
                      cwd: Path | None = None, timeout: int = 300,
                      env: dict | None = None) -> CheckResult:
        cwd = cwd or REPO_ROOT
        check.started_at = now_iso()
        check.timeout_seconds = timeout

        result = run_command(cmd, cwd, timeout, env)
        check.exit_code = result["exit_code"]
        check.duration_seconds = result["duration_seconds"]
        check.completed_at = now_iso()

        log_content = (
            f"--- NEXARA CI Authority Check ---\n"
            f"check_id: {check.check_id}\n"
            f"command: {shlex.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"exit_code: {check.exit_code}\n"
            f"--- STDOUT ---\n{redact(result['stdout'])}\n"
            f"--- STDERR ---\n{redact(result['stderr'])}\n"
            f"--- END ---\n"
        )

        log_file = self.log_dir / f"{check.check_id}.log"
        log_file.write_text(log_content)
        check.log_path = str(log_file.relative_to(REPO_ROOT))
        check.log_sha256 = sha256_file(log_file)
        check.stderr_present = bool(result["stderr"].strip())

        if check.exit_code == 0:
            check.status = "PASS"
        elif check.exit_code in (-1, -2):
            check.status = "ERROR"
        else:
            check.status = "FAIL"

        return check

    def check_python_tests(self) -> CheckResult:
        c = CheckResult("python_tests", "Python Tests",
                        "python3 -m pytest tests/ -q", str(REPO_ROOT))
        c.tool_versions["python"] = self._tool_version(["python3", "--version"])
        self.execute_check(c, ["python3", "-m", "pytest", "tests/", "-q"],
                           timeout=600)
        return c

    def check_python_ruff(self) -> CheckResult:
        c = CheckResult("python_ruff", "Python Ruff (full src+tests)",
                        "ruff check src tests", str(REPO_ROOT))
        c.tool_versions["ruff"] = self._tool_version(["python3", "-m", "ruff", "--version"])
        c.limitations.append("pre-existing repository ruff debt: 1228 lines in old modules")
        self.execute_check(c, ["python3", "-m", "ruff", "check", "src", "tests"],
                           timeout=120)
        return c

    def check_python_compileall(self) -> CheckResult:
        c = CheckResult("python_compileall", "Python Compileall",
                        "python3 -m compileall -q src/nexara_prime", str(REPO_ROOT))
        self.execute_check(c, ["python3", "-m", "compileall", "-q",
                                "src/nexara_prime"], timeout=60)
        return c

    def check_typescript(self) -> CheckResult:
        ts_dir = REPO_ROOT / "platform" / "sdk" / "typescript"
        has_lock = (ts_dir / "package-lock.json").exists()
        if not has_lock:
            c = CheckResult("typescript", "TypeScript CI",
                            "npm ci && npx tsc --noEmit", str(ts_dir),
                            "NOT_APPLICABLE_WITH_EVIDENCE",
                            "no package-lock.json found")
            c.status = "NOT_APPLICABLE_WITH_EVIDENCE"
            return c
        c = CheckResult("typescript_install", "TypeScript: npm ci",
                        "npm ci", str(ts_dir))
        self.execute_check(c, ["npm", "ci"], cwd=ts_dir, timeout=120)
        if c.exit_code != 0:
            return c

        c2 = CheckResult("typescript_typecheck", "TypeScript: tsc --noEmit",
                         "npx tsc --noEmit", str(ts_dir))
        self.execute_check(c2, ["npx", "tsc", "--noEmit"], cwd=ts_dir, timeout=120)
        c2.tool_versions["node"] = self._tool_version(["node", "--version"])
        c2.tool_versions["npm"] = self._tool_version(["npm", "--version"])
        return c2

    def check_swift_macos(self) -> CheckResult:
        nc_dir = REPO_ROOT / "experience" / "NexaraCore"
        if not (nc_dir / "Package.swift").exists():
            c = CheckResult("swift_macos", "Swift macOS Build",
                            "swift build", str(nc_dir),
                            "NOT_APPLICABLE_WITH_EVIDENCE",
                            "NexaraCore Package.swift not found")
            c.status = "NOT_APPLICABLE_WITH_EVIDENCE"
            return c
        c = CheckResult("swift_macos", "Swift macOS Build",
                        "CODE_SIGNING_ALLOWED=NO swift build", str(nc_dir))
        c.limitations.append("macOS-only; not applicable on Linux runners")
        self.execute_check(c, ["swift", "build"], cwd=nc_dir, timeout=300,
                           env={"CODE_SIGNING_ALLOWED": "NO"})
        c.tool_versions["swift"] = self._tool_version(["swift", "--version"])
        if c.exit_code == 0:
            c.tool_versions["xcode"] = self._tool_version(["xcodebuild", "-version"])
        return c

    def check_swift_ios(self) -> CheckResult:
        ios_dir = REPO_ROOT / "experience" / "ios"
        has_xcodeproj = any((ios_dir).glob("*.xcodeproj")) if ios_dir.exists() else False
        has_spm = (ios_dir / "Package.swift").exists() if ios_dir.exists() else False
        if not has_xcodeproj and not has_spm:
            c = CheckResult("swift_ios", "Swift iOS Build (xcodebuild)",
                            "xcodebuild ...", str(ios_dir),
                            "NOT_APPLICABLE_WITH_EVIDENCE",
                            "no .xcodeproj or Package.swift found in experience/ios")
            c.status = "NOT_APPLICABLE_WITH_EVIDENCE"
            return c
        if has_spm and not has_xcodeproj:
            c = CheckResult("swift_ios", "Swift iOS Build (SPM, no xcodeproj)",
                            "swift build", str(ios_dir),
                            "NOT_APPLICABLE_WITH_EVIDENCE",
                            "SPM-only iOS target: no .xcodeproj for xcodebuild CI; "
                            "swift build compiles as macOS due to .macOS(.v14) platform")
            c.limitations.append("CI workflow uses xcodebuild which requires .xcodeproj")
            c.limitations.append("swift build works but does not produce iOS simulator binary")
            c.status = "NOT_APPLICABLE_WITH_EVIDENCE"
            return c
        c = CheckResult("swift_ios", "Swift iOS Build",
                        "swift build", str(ios_dir))
        self.execute_check(c, ["swift", "build"], cwd=ios_dir, timeout=300,
                           env={"CODE_SIGNING_ALLOWED": "NO"})
        return c

    def check_governance(self) -> CheckResult:
        script = REPO_ROOT / "scripts" / "governance" / "detect_state_drift.py"
        if not script.exists():
            c = CheckResult("governance", "Governance: State Drift Detection",
                            str(script), str(REPO_ROOT),
                            "SKIPPED_WITH_BLOCKER", "script not found")
            c.status = "SKIPPED_WITH_BLOCKER"
            return c
        c = CheckResult("governance", "Governance: State Drift Detection",
                        "python3 scripts/governance/detect_state_drift.py",
                        str(REPO_ROOT))
        c.limitations.append("script exits 0 even on drift — non-blocking by its own contract")
        self.execute_check(c, ["python3", str(script.relative_to(REPO_ROOT))],
                           timeout=60)
        return c

    def check_secrets(self) -> CheckResult:
        script = REPO_ROOT / "scripts" / "security" / "scan_hardcoded_secrets.py"
        if not script.exists():
            c = CheckResult("secret_scan", "Secret Scan",
                            str(script), str(REPO_ROOT),
                            "SKIPPED_WITH_BLOCKER", "script not found")
            c.status = "SKIPPED_WITH_BLOCKER"
            return c
        c = CheckResult("secret_scan", "Secret Scan",
                        "python3 scripts/security/scan_hardcoded_secrets.py",
                        str(REPO_ROOT))
        self.execute_check(c, ["python3", str(script.relative_to(REPO_ROOT))],
                           timeout=60)
        return c

    def check_workflow_integrity(self) -> CheckResult:
        c = CheckResult("workflow_integrity", "Workflow Integrity Audit",
                        "yaml parse + git diff --check + anti-weakening scan",
                        str(REPO_ROOT))
        wf_dir = REPO_ROOT / ".github" / "workflows"
        issues: list[str] = []

        # YAML parse
        import yaml
        for wf in sorted(wf_dir.glob("*.yml")):
            try:
                with open(wf) as f:
                    yaml.safe_load(f)
            except Exception:
                import traceback
                issues.append(f"YAML parse error in {wf.name}: {traceback.format_exc()[:200]}")

        # git diff --check
        r = subprocess.run(["git", "diff", "--check"], capture_output=True,
                           text=True, cwd=REPO_ROOT, timeout=10)
        if r.returncode != 0:
            issues.append(f"git diff --check failed: {r.stderr[:200]}")

        # Anti-weakening scan
        for wf in sorted(wf_dir.glob("*.yml")):
            content = wf.read_text()
            for pattern, desc in [
                ("continue-on-error:", "continue-on-error found"),
                ("|| true", "|| true failure swallow found"),
                ("|| echo", "|| echo failure swallow found"),
            ]:
                if pattern in content:
                    line_nums = [str(i+1) for i, line in enumerate(content.split("\n"))
                                 if pattern in line]
                    issues.append(f"{wf.name}: {desc} at lines {','.join(line_nums)}")

        # Shell anti-patterns in workflows
        for wf in sorted(wf_dir.glob("*.yml")):
            content = wf.read_text()
            if "set +e" in content:
                line_nums = [str(i+1) for i, line in enumerate(content.split("\n"))
                             if "set +e" in line]
                issues.append(f"{wf.name}: set +e at lines {','.join(line_nums)}")

        c.exit_code = 1 if issues else 0
        c.status = "FAIL" if issues else "PASS"

        log_content = (
            f"--- Workflow Integrity Audit ---\n"
            f"scanned: {len(list(wf_dir.glob('*.yml')))} workflows\n"
        )
        if issues:
            log_content += "ISSUES:\n" + "\n".join(f"  - {i}" for i in issues) + "\n"
        else:
            log_content += "No integrity issues found.\n"
        log_content += "--- END ---\n"

        log_file = self.log_dir / "workflow_integrity.log"
        log_file.write_text(log_content)
        c.log_path = str(log_file.relative_to(REPO_ROOT))
        c.log_sha256 = sha256_file(log_file)
        c.started_at = now_iso()
        c.completed_at = now_iso()
        c.stderr_present = bool(issues)
        c.limitations.append("|| true in audit grep commands is for grep 'no match' safety only")
        return c

    def check_authority_unit_tests(self) -> CheckResult:
        c = CheckResult("authority_unit_tests", "Authority Unit Tests",
                        "python3 -m pytest tests/ci/ -q", str(REPO_ROOT))
        test_dir = REPO_ROOT / "tests" / "ci"
        if not test_dir.exists() or not list(test_dir.glob("test_*.py")):
            c.applicability = "SKIPPED_WITH_BLOCKER"
            c.applicability_reason = "no authority test files found"
            c.status = "SKIPPED_WITH_BLOCKER"
            return c
        self.execute_check(c, ["python3", "-m", "pytest", "tests/ci/", "-q"],
                           timeout=60)
        return c

    def check_receipt_verification(self) -> CheckResult:
        c = CheckResult("receipt_verification", "Receipt Self-Verification",
                        "internal receipt integrity check", str(REPO_ROOT))
        c.started_at = now_iso()
        errors = []

        # Verify all logs exist and hashes match
        for check in self.checks:
            if check.log_path:
                log_file = REPO_ROOT / check.log_path
                if not log_file.exists():
                    errors.append(f"missing log: {check.log_path}")
                else:
                    actual = sha256_file(log_file)
                    if actual != check.log_sha256:
                        errors.append(f"log hash mismatch: {check.log_path}")

        c.exit_code = 1 if errors else 0
        c.status = "FAIL" if errors else "PASS"
        c.completed_at = now_iso()
        c.duration_seconds = 0
        c.stderr_present = bool(errors)
        return c

    def run_all(self):
        check_factories = [
            self.check_python_tests,
            self.check_python_ruff,
            self.check_python_compileall,
            self.check_typescript,
            self.check_swift_macos,
            self.check_swift_ios,
            self.check_governance,
            self.check_secrets,
            self.check_workflow_integrity,
            self.check_authority_unit_tests,
        ]

        for factory in check_factories:
            try:
                c = factory()
                self.checks.append(c)
                if self.fail_fast and c.status in ("FAIL", "ERROR"):
                    break
            except Exception:
                err = CheckResult("error", f"Authority Error: {factory.__name__}",
                                  "", str(REPO_ROOT))
                err.status = "ERROR"
                err.stderr_present = True
                self.checks.append(err)

        # Receipt verification
        receipt_check = self.check_receipt_verification()
        self.checks.append(receipt_check)

        self._generate_receipt()

    def _overall_status(self) -> str:
        statuses = {c.status for c in self.checks}
        if "FAIL" in statuses or "ERROR" in statuses:
            return "FAIL"
        if "SKIPPED_WITH_BLOCKER" in statuses:
            return "FAIL"
        has_na = "NOT_APPLICABLE_WITH_EVIDENCE" in statuses
        all_ok = statuses <= {"PASS", "NOT_APPLICABLE_WITH_EVIDENCE"}
        if all_ok and has_na:
            return "CONDITIONAL_PASS"
        if all_ok:
            return "PASS"
        return "FAIL"

    def _generate_receipt(self):
        status = self._overall_status()
        worktree_clean = self._is_worktree_clean()
        local_remote_match = (self.head == self.remote_head)

        branch = self._check_branch()
        hostname = platform.node()

        check_dicts = [c.to_dict() for c in self.checks]

        payload = {
            "schema_version": SCHEMA_VERSION,
            "authority_version": AUTHORITY_VERSION,
            "authority_mode": "precommit" if self.precommit else "final",
            "evidence_class": EVIDENCE_CLASS,
            "repository": "Zsx154855/NEXARA-PRIME",
            "branch": branch,
            "pr_number": 13,
            "initial_frozen_head": "895d8d4475bb398e799461bee87f7a81334748e8",
            "validated_head": self.head,
            "remote_head": self.remote_head,
            "worktree_clean": worktree_clean,
            "local_remote_match": local_remote_match,
            "run_id": self.run,
            "started_at": self.started_at,
            "completed_at": now_iso(),
            "host_os": platform.system(),
            "host_arch": platform.machine(),
            "hostname_redacted": sha256_text(hostname)[:16],
            "python_version": self._tool_version(["python3", "--version"]),
            "node_version": self._tool_version(["node", "--version"]),
            "npm_version": self._tool_version(["npm", "--version"]),
            "swift_version": self._tool_version(["swift", "--version"]),
            "xcode_version": self._tool_version(["xcodebuild", "-version"]),
            "github_actions_billing_lock": True,
            "github_self_hosted_probe_result": "NOT_RUN",
            "billing_lock_blocks_self_hosted": "UNKNOWN",
            "checks": check_dicts,
            "overall_status": status,
            "limitations": [
                "GitHub-hosted Jobs have never executed on this branch",
                "GitHub Actions billing lock blocks all hosted runners",
                "Local Authority PASS != GitHub required checks green",
                "Full-repo ruff check includes 1228 lines of pre-existing debt",
                "iOS CI has no .xcodeproj; SPM-only target cannot run xcodebuild",
                "Governance script exits 0 on drift by its own contract",
            ],
            "known_preexisting_debt": [
                "1228 ruff issues in pre-existing modules",
            ],
            "not_applicable_items": [
                c.check_id for c in self.checks
                if c.status == "NOT_APPLICABLE_WITH_EVIDENCE"
            ],
            "blocking_items": [
                c.check_id for c in self.checks if c.status == "FAIL"
            ],
            "owner_approval_required_for_mark_ready": True,
            "owner_approval_required_for_merge": True,
            "github_required_checks_green": False,
            "local_pass_claimed_as_github_pass": False,
        }

        # Check for previous receipt MUST happen before hash computation
        latest = RUNTIME_DIR / "latest.json"
        previous_hash = ""
        if latest.exists():
            try:
                prev = json.loads(latest.read_text())
                previous_hash = prev.get("receipt_file_sha256", "")
            except Exception:
                pass

        payload["previous_receipt_sha256"] = previous_hash
        payload["hash_chain_status"] = (
            "CONTINUOUS" if previous_hash else "FIRST_RECEIPT"
        )

        # Compute canonical payload hash LAST — after ALL content fields
        from scripts.ci.receipt_hash import compute_payload_sha256, compute_file_sha256  # noqa: E402
        payload["receipt_payload_sha256"] = compute_payload_sha256(payload)

        # Write receipt, compute file hash, finalize
        receipt_path = self.receipt_dir / "authority-receipt.json"
        receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        payload["receipt_file_sha256"] = compute_file_sha256(receipt_path)
        receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

        # Write latest pointer
        latest.write_text(json.dumps({
            "run_id": self.run, "status": status, "head": self.head,
            "completed_at": payload["completed_at"],
            "receipt_path": str(receipt_path.relative_to(REPO_ROOT)),
            "receipt_sha256": payload["receipt_file_sha256"],
        }, indent=2))

        # MD report
        md_path = self.receipt_dir / "authority-receipt.md"
        lines = [
            "# NEXARA CI Authority Receipt",
            f"**Run:** {self.run}",
            f"**Status:** {status}",
            f"**HEAD:** {self.head}",
            f"**Evidence Class:** {EVIDENCE_CLASS}",
            f"**Precommit:** {self.precommit}",
            "",
            "## Checks",
        ]
        for c in self.checks:
            lines.append(f"- [{c.status}] {c.name} (exit={c.exit_code})")
        lines.extend([
            "",
            "## Hash Chain",
            f"- receipt_payload_sha256: `{payload['receipt_payload_sha256']}`",
            f"- receipt_file_sha256: `{payload['receipt_file_sha256']}`",
            f"- previous_receipt_sha256: `{previous_hash or 'FIRST'}`",
            f"- hash_chain_status: `{payload['hash_chain_status']}`",
        ])
        md_path.write_text("\n".join(lines) + "\n")

        self._receipt = payload

    @property
    def receipt(self) -> dict:
        return getattr(self, "_receipt", {})


def main():
    parser = argparse.ArgumentParser(description="NEXARA Local CI Authority")
    parser.add_argument("--full", action="store_true", help="Run all checks")
    parser.add_argument("--evidence", action="store_true", help="Generate evidence receipt")
    parser.add_argument("--head", default="", help="Expected HEAD SHA")
    parser.add_argument("--precommit", action="store_true", help="Pre-commit validation mode")
    parser.add_argument("--fail-fast", action="store_true", default=False)
    args = parser.parse_args()

    authority = NexaraCiAuthority(
        head=args.head, precommit=args.precommit, fail_fast=args.fail_fast,
    )

    # Pre-flight
    print(f"=== NEXARA CI Authority {AUTHORITY_VERSION} ===")
    print(f"HEAD: {authority.head}")
    print(f"Remote: {authority.remote_head}")
    print(f"Run: {authority.run}")
    print(f"Precommit: {authority.precommit}")

    if args.head and authority.head != args.head:
        print(f"FATAL: HEAD mismatch. Expected {args.head}, actual {authority.head}")
        sys.exit(1)

    authority.run_all()

    receipt = authority.receipt
    print(f"\nStatus: {receipt.get('overall_status', 'UNKNOWN')}")
    print(f"Checks: {len(authority.checks)}")
    for c in authority.checks:
        print(f"  [{c.status}] {c.name}")
    print(f"\nReceipt: {authority.receipt_dir / 'authority-receipt.json'}")
    print(f"Payload SHA-256: {receipt.get('receipt_payload_sha256', 'N/A')}")
    print(f"File SHA-256: {receipt.get('receipt_file_sha256', 'N/A')}")

    if receipt.get("overall_status") == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
