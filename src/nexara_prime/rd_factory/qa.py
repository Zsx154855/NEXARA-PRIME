"""Verification: deterministic exit-code gates plus an independent adversarial QA run.

Nothing passes on a self-report. A gate passes only when its process exits 0,
and the QA verdict is fail-closed: an unparsable or ambiguous answer rejects.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class GateCommand:
    name: str
    argv: tuple[str, ...]
    timeout_s: float = 900.0


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    exit_code: int | None
    tail: str

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "exit_code": self.exit_code}


@dataclass(frozen=True)
class GateReport:
    passed: bool
    results: tuple[GateResult, ...]
    checked_at: str

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checked_at": self.checked_at,
            "results": [item.as_dict() for item in self.results],
        }

    def summary(self) -> str:
        failures = [
            item.name + "(exit=" + str(item.exit_code) + "): " + item.tail
            for item in self.results
            if not item.passed
        ]
        return " | ".join(failures)[:1200]


def scoped_secret_script(base_ref: str) -> str:
    """Secret scan limited to the files this task changed.

    Both governance scripts derive their repository root from __file__, and the
    checked-out tree already carries findings, so an unscoped run fails every task
    no matter what the engineer did. Gate paths stay relative so the scripts resolve
    the worktree, not the developer checkout.
    """
    return (
        "import re, subprocess, sys\n"
        "changed = set(subprocess.run(['git', 'diff', '--name-only', '"
        + base_ref
        + "...HEAD'], capture_output=True, text=True).stdout.split())\n"
        "proc = subprocess.run([sys.executable, 'scripts/security/scan_hardcoded_secrets.py'],"
        " capture_output=True, text=True)\n"
        "pattern = re.compile(r'^\\s+(\\S+?):(\\d+)\\s')\n"
        "hits = [line.strip() for line in proc.stdout.splitlines()"
        " if (match := pattern.match(line)) and match.group(1) in changed]\n"
        "print('scoped secret findings:', hits[:5])\n"
        "sys.exit(1 if hits else 0)\n"
    )


class DeterministicGates:
    """Runs repository checks inside the task worktree and trusts only exit codes."""

    def __init__(self, commands: Sequence[GateCommand], python: str = "python3"):
        self.commands = tuple(commands)
        self.python = python

    @classmethod
    def default(
        cls,
        repo: str | Path,
        test_paths: Sequence[str] = ("tests",),
        base_ref: str = "main",
    ) -> DeterministicGates:
        repo_path = Path(repo)
        candidate = repo_path / ".venv" / "bin" / "python"
        interpreter = str(candidate) if candidate.exists() else "python3"
        ruff = repo_path / ".venv" / "bin" / "ruff"
        commands = [
            GateCommand(
                "whitespace",
                ("bash", "-c", "git diff --check " + base_ref + "...HEAD"),
                timeout_s=120,
            )
        ]
        if ruff.exists():
            script = (
                "files=$(git diff --name-only " + base_ref + "...HEAD -- '*.py' | tr '\\n' ' '); "
                "if [ -z \"$files\" ]; then echo 'no python files changed'; exit 0; fi; "
                + str(ruff)
                + " check $files"
            )
            commands.append(GateCommand("ruff", ("bash", "-c", script), timeout_s=300))
        nsec = repo_path / "scripts" / "governance" / "validate_nsec.py"
        if nsec.exists():
            commands.append(
                GateCommand(
                    "nsec",
                    (interpreter, "scripts/governance/validate_nsec.py"),
                    timeout_s=300,
                )
            )
        secrets = repo_path / "scripts" / "security" / "scan_hardcoded_secrets.py"
        if secrets.exists():
            commands.append(
                GateCommand(
                    "secrets",
                    (interpreter, "-c", scoped_secret_script(base_ref)),
                    timeout_s=300,
                )
            )
        commands.append(
            GateCommand("pytest", (interpreter, "-m", "pytest", "-q", *test_paths), timeout_s=1800)
        )
        return cls(commands, python=interpreter)

    def run(self, worktree: str | Path) -> GateReport:
        root = Path(worktree)
        env = {**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
        results: list[GateResult] = []
        for command in self.commands:
            try:
                proc = subprocess.run(
                    list(command.argv),
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=command.timeout_s,
                )
                tail = (proc.stdout + proc.stderr).strip()[-600:]
                results.append(
                    GateResult(
                        name=command.name,
                        passed=proc.returncode == 0,
                        exit_code=proc.returncode,
                        tail=tail,
                    )
                )
            except subprocess.TimeoutExpired:
                results.append(
                    GateResult(command.name, False, None, "timed out after " + str(command.timeout_s) + "s")
                )
            except OSError as exc:
                results.append(GateResult(command.name, False, None, "unavailable: " + str(exc)))
        return GateReport(
            passed=all(item.passed for item in results),
            results=tuple(results),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )


@dataclass(frozen=True)
class QAVerdict:
    approved: bool
    findings: tuple[str, ...]
    evidence: tuple[str, ...]
    parse_ok: bool
    raw: str

    def as_dict(self) -> dict:
        return {
            "approved": self.approved,
            "findings": list(self.findings),
            "evidence": list(self.evidence),
            "parse_ok": self.parse_ok,
            "raw": self.raw[-2000:],
        }


_QA_PROMPT = """You are the independent QA reviewer of an autonomous factory.

You did not write this change and you do not trust the author's claims. Decide
whether the diff below may be delivered as a Draft PR.

Objective:
{objective}

Acceptance criteria the factory wrote:
{acceptance}

Deterministic gate results (exit codes are already authoritative):
{gates}

Diff under review, delimited by @@DIFF@@:
@@DIFF@@
{diff}
@@END DIFF@@

Rules:
- Read the worktree to confirm behaviour; you may run read-only commands and the
  test suite, but you must not modify any file.
- Reject if the diff does not actually satisfy a criterion, if a gate is only
  satisfied by weakening a test, or if the change reaches outside its scope.
- Answer with ONE JSON object and nothing after it:
  {{"verdict": "approve" or "reject", "findings": ["..."], "evidence": ["..."]}}
"""


class IndependentQA:
    """Adversarial review by a separate session that never sees the executor transcript."""

    def __init__(self, runner: Callable[[str, Path], str]):
        self._runner = runner

    @classmethod
    def headless(
        cls,
        *,
        profile: str = "headless",
        dsh_bin: str = "dsh",
        timeout_s: float = 1800.0,
        permission_mode: str = "danger-full-access",
    ) -> IndependentQA:
        def run(prompt: str, worktree: Path) -> str:
            env = {**os.environ, "DSH_PERMISSION_MODE": permission_mode}
            proc = subprocess.run(
                [dsh_bin, "--profile", profile, "-"],
                cwd=str(worktree),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
            )
            return proc.stdout

        return cls(run)

    @classmethod
    def claude(
        cls,
        *,
        claude_bin: str = "claude",
        timeout_s: float = 1800.0,
        permission_mode: str = "bypassPermissions",
        model: str | None = None,
    ) -> IndependentQA:
        def run(prompt: str, worktree: Path) -> str:
            cmd = [
                claude_bin,
                "-p",
                prompt,
                "--output-format",
                "text",
                "--permission-mode",
                permission_mode,
            ]
            if model:
                cmd += ["--model", model]
            proc = subprocess.run(
                cmd,
                cwd=str(worktree),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return proc.stdout

        return cls(run)

    def review(
        self,
        *,
        objective: str,
        acceptance: Sequence[str],
        diff: str,
        gates: GateReport,
        worktree: Path,
    ) -> QAVerdict:
        prompt = _QA_PROMPT.format(
            objective=objective,
            acceptance="\n".join("- " + item for item in acceptance) or "- none declared",
            gates=json.dumps(gates.as_dict(), ensure_ascii=False),
            diff=diff[:20000] or "(empty diff)",
        )
        try:
            text = self._runner(prompt, worktree)
        except Exception as exc:  # a broken reviewer must never approve
            return QAVerdict(False, ("reviewer failed: " + str(exc),), (), False, "")
        return self.parse(text)

    @staticmethod
    def parse(text: str) -> QAVerdict:
        payload = _last_json_object(text)
        if payload is None:
            return QAVerdict(False, ("unparsable QA answer",), (), False, text)
        verdict = str(payload.get("verdict", "")).strip().lower()
        findings = tuple(str(item) for item in payload.get("findings", []) or [])
        evidence = tuple(str(item) for item in payload.get("evidence", []) or [])
        if verdict not in ("approve", "reject"):
            return QAVerdict(False, ("unknown verdict",) + findings, evidence, False, text)
        return QAVerdict(verdict == "approve", findings, evidence, True, text)


def _last_json_object(text: str) -> dict | None:
    starts = [index for index, char in enumerate(text) if char == "{"]
    for start in reversed(starts):
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(candidate, dict) and "verdict" in candidate:
                        return candidate
                    break
    return None
