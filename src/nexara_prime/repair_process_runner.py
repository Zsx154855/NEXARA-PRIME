"""Host-controlled local repair runner for an explicitly isolated Git worktree.

This is a zero-network subprocess implementation, NOT an OS security sandbox.
Operate only in a disposable/authorized worktree. Never pass production secrets.
The authority captures process output; callbacks cannot submit their own scores.
"""

from __future__ import annotations

import base64
import hashlib
import os
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from .repair_loop import RepairContract, RepairResult


class LocalRepairProcessRunner:
    """Run git-apply, create a local isolated-worktree commit and run real pytest.

    The orchestrator, not an untrusted patch callback, must own this object and
    its process observation registry. Observations survive only this process;
    after a restart acceptance fails closed until a durable authority is built.
    """

    def __init__(
        self,
        *,
        worktree: Path,
        mission_id: str,
        evidence_store: Any,
        patch_diff: str,
        pytest_targets: tuple[str, ...],
        timeout_s: int = 90,
        max_log_bytes: int = 262144,
    ) -> None:
        self.worktree = Path(worktree).resolve(strict=True)
        self.mission_id = mission_id
        self.evidence = evidence_store
        self.patch_diff = patch_diff
        self.pytest_targets = pytest_targets
        self.timeout_s = timeout_s
        self.max_log_bytes = max_log_bytes
        self._observed: dict[str, dict[str, Any]] = {}
        if not (1 <= timeout_s <= 900) or not pytest_targets:
            raise ValueError("invalid_execution_limits")
        if not all(re.fullmatch(r"tests/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_]+)*", t) for t in pytest_targets):
            raise ValueError("pytest_targets_not_allowlisted")
        branch = self._git("branch", "--show-current").stdout.strip()
        if not (branch.startswith("fix/") or branch.startswith("repair/") or branch.startswith("agent/")):
            raise ValueError("isolated_worktree_branch_required")
        self._base = self._git("rev-parse", "HEAD").stdout.strip()
        if self._git("status", "--porcelain").stdout.strip():
            raise ValueError("worktree_not_clean")

    def _git(self, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.worktree, input=input_text, text=True,
            capture_output=True, timeout=self.timeout_s, check=True,
        )

    def verify_process(self, payload: dict[str, Any]) -> bool:
        """Check controller-owned observation and persisted local Git commit.

        This authenticates against a separate in-process controller registry,
        not against a malicious host or a compromised controller.
        """
        run_id = payload.get("run_id")
        try:
            raw_log = base64.b64decode(payload["test_log_b64"], validate=True)
            if hashlib.sha256(raw_log).hexdigest() != payload["test_log_sha256"]:
                return False
        except (KeyError, TypeError, ValueError):
            return False
        if not isinstance(run_id, str) or self._observed.get(run_id) != payload:
            return False
        try:
            self._git("cat-file", "-e", f"{payload['post_commit']}^{{commit}}")
            parent = self._git("rev-parse", f"{payload['post_commit']}^").stdout.strip()
            return parent == payload["base_commit"]
        except (subprocess.SubprocessError, KeyError, ValueError):
            return False

    def __call__(self, contract: RepairContract) -> RepairResult:
        """Called only by RepairLoop after its governance review."""
        did_apply = False

        def fail(error: str) -> RepairResult:
            return RepairResult(contract_id=contract.contract_id, error=error, patch_applied=did_apply)

        if self.evidence is None:
            return fail("repair_evidence_store_unavailable")
        try:
            if self._git("rev-parse", "HEAD").stdout.strip() != self._base:
                return fail("repair_worktree_already_changed")
            if self._git("status", "--porcelain").stdout.strip():
                return fail("repair_worktree_not_clean")
            if not self.patch_diff.strip():
                return fail("repair_patch_missing")
            self._git("apply", "--check", "-", input_text=self.patch_diff)
            self._git("apply", "-", input_text=self.patch_diff)
            did_apply = True
            diff = self._git("diff", "--binary").stdout
            changed = set(self._git("diff", "--name-only").stdout.splitlines())
            if not diff or not changed:
                return fail("repair_patch_no_effect")
            if not changed.issubset(set(contract.affected_files)):
                return fail("repair_patch_outside_contract_scope")
            patch_digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
            self._git("add", "--", *sorted(changed))
            self._git("-c", "user.name=NEXARA Test Runner", "-c",
                      "user.email=runner@localhost", "commit", "--no-verify", "-m",
                      f"repair receipt {contract.contract_id}")
            post_commit = self._git("rev-parse", "HEAD").stdout.strip()
            run_id = uuid4().hex
            cmd = [sys.executable, "-m", "pytest", "-q", *self.pytest_targets]
            env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "HOME", "VIRTUAL_ENV") if k in os.environ}
            env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            completed = subprocess.run(
                cmd, cwd=self.worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=self.timeout_s, env=env, check=False,
            )
            log = completed.stdout or b""
            if len(log) > self.max_log_bytes:
                return fail("repair_test_log_over_limit")
            found = re.search(rb"(?:^|\s)(\d+) passed(?:\s|,|$)", log)
            passed = int(found.group(1)) if found else 0
            log_digest = hashlib.sha256(log).hexdigest()
            payload = {
                "mission_id": self.mission_id,
                "contract_id": contract.contract_id,
                "failure_id": contract.failure_id,
                "contract_digest": contract.contract_digest,
                "attempt_number": contract.attempt_number,
                "tool_invocation_id": run_id,
                "tests_passed": passed,
                "tests_failed": 0 if completed.returncode == 0 else 1,
                "test_exit_code": completed.returncode,
                "patch_applied": True,
                "run_id": run_id,
                "test_command": " ".join(cmd),
                "executor_id": "local-repair-process-runner",
                "patch_sha256": patch_digest,
                "test_log_sha256": log_digest,
                "test_log_b64": base64.b64encode(log).decode("ascii"),
                "base_commit": self._base,
                "post_commit": post_commit,
            }
            artifact = self.evidence.add(
                self.mission_id, "repair_execution_receipt", "real repair process",
                json.dumps(payload, sort_keys=True), f"repair:{run_id}",
                task_id=contract.contract_id, tool_invocation_id=run_id,
                actor="local-repair-process-runner", source="host-subprocess",
                idempotency_key=f"repair:{self.mission_id}:{contract.contract_id}:{run_id}",
            )
            if self.evidence.verify(artifact.evidence_id) is not True:
                return fail("repair_evidence_verification_failed")
            # Only register a successful observed process; a failure receipt is
            # persisted for debugging but cannot become evidence of success.
            if completed.returncode != 0 or passed <= 0:
                return fail("repair_tests_failed_or_missing")
            self._observed[run_id] = payload.copy()
            return RepairResult(
                contract_id=contract.contract_id, success=True, patch_applied=True,
                tests_passed=passed, evidence_ids=[artifact.evidence_id],
            )
        except subprocess.TimeoutExpired:
            return fail("repair_process_timeout")
        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            return fail(f"repair_process_failed:{type(exc).__name__}")
