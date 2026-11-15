"""Orchestration: claim, execute, test, self-repair, independent QA, Draft PR."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .executor import ExecResult, ExecutorError, WorktreeManager, changed_files, diff_sha256
from .ledger import Claim, TaskLedger
from .qa import DeterministicGates, GateReport, IndependentQA, QAVerdict
from .recovery import recover
from .remote import RemoteGate


_ENGINEER_PROMPT = """You are the engineer agent of the NEXARA R&D factory, working in an isolated git worktree.

Task: {title}

Objective:
{objective}

Acceptance criteria that must each be demonstrably true when you finish:
{acceptance}

Files or modules you may touch:
{scope}

Hard constraints:
- Never merge, never push to main, never open a non-draft PR.
- No new paid services, no production deploys, no permanent daemons.
- Do not weaken, delete or skip tests to make them pass.
- Run the relevant tests yourself before you stop.
{feedback}

When you are done, state what changed and which commands you ran.
"""


@dataclass(frozen=True)
class FactoryRun:
    task_id: str
    state: str
    pr_url: str | None
    notes: tuple[str, ...]
    attempt_token: str

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "state": self.state,
            "pr_url": self.pr_url,
            "notes": list(self.notes),
            "attempt_token": self.attempt_token,
        }


class RDFactory:
    """One unattended control loop over a durable ledger."""

    def __init__(
        self,
        *,
        ledger: TaskLedger,
        executor,
        worktrees: WorktreeManager,
        gates: DeterministicGates,
        qa: IndependentQA,
        repo: str | Path,
        publisher=None,
        worker: str = "nexara",
        lease_ttl_s: int = 1800,
        max_repairs: int = 1,
        remote: RemoteGate | None = None,
        require_remote: bool = False,
        log_dir: str | Path | None = None,
    ):
        self.ledger = ledger
        self.executor = executor
        self.worktrees = worktrees
        self.gates = gates
        self.qa = qa
        self.repo = Path(repo)
        self.publisher = publisher
        self.worker = worker
        self.lease_ttl_s = lease_ttl_s
        self.max_repairs = max_repairs
        self.remote = remote if remote is not None else RemoteGate()
        self.require_remote = require_remote
        self.log_dir = Path(log_dir) if log_dir else self.repo / "runtime" / "factory" / "logs"

    def status(self) -> dict:
        report = recover(self.ledger)
        return {
            "worker": self.worker,
            "stats": self.ledger.stats(),
            "recovery": report.as_dict(),
            "remote": self.remote.policy(),
            "recent_events": self.ledger.events(None, limit=5),
        }

    def run_until_idle(self, max_tasks: int = 3) -> list[FactoryRun]:
        runs: list[FactoryRun] = []
        for _ in range(max_tasks):
            run = self.run_once()
            if run is None:
                break
            runs.append(run)
            if run.state in ("blocked", "failed"):
                break
        return runs

    def run_once(self) -> FactoryRun | None:
        report = recover(self.ledger)
        if self.require_remote and not self.remote.available():
            claim = self.ledger.claim(self.worker, self.lease_ttl_s)
            if claim is None:
                return None
            self.ledger.release(claim.task_id, claim.attempt_token, "no authorized remote executor")
            return FactoryRun(
                claim.task_id,
                "queued",
                None,
                ("no authorized remote executor: task returned to the queue",),
                claim.attempt_token,
            )

        claim = self.ledger.claim(self.worker, self.lease_ttl_s)
        if claim is None:
            return None
        notes: list[str] = []
        if report.requeued:
            notes.append("reaped " + str(len(report.requeued)) + " expired lease(s)")
        return self._execute_claim(claim, notes)

    def _execute_claim(self, claim: Claim, notes: list[str]) -> FactoryRun:
        branch = claim.branch or ("factory/" + claim.task_id)
        worktree = self.worktrees.prepare(claim.task_id, branch)
        self.ledger.mark_running(
            claim.task_id, claim.attempt_token, branch=branch, worktree=str(worktree)
        )
        feedback = ""
        gate_report: GateReport | None = None
        execution: ExecResult | None = None

        for round_index in range(self.max_repairs + 1):
            self.ledger.renew(claim.task_id, claim.attempt_token, self.lease_ttl_s)
            prompt = self._engineer_prompt(claim, feedback)
            execution = self.executor.execute(
                worktree, prompt, self._log_path(claim, round_index)
            )
            self.ledger.record_receipt(
                claim.task_id,
                claim.attempt_token,
                "execution",
                {**execution.as_receipt(), "round": round_index},
            )
            if execution.timed_out:
                self.ledger.release(
                    claim.task_id,
                    claim.attempt_token,
                    "timeout after " + str(int(execution.duration_s)) + "s",
                )
                notes.append("timeout: process group killed, task returned to queue")
                return FactoryRun(claim.task_id, "queued", None, tuple(notes), claim.attempt_token)
            if not changed_files(worktree):
                self.ledger.finish(
                    claim.task_id,
                    claim.attempt_token,
                    "failed",
                    error="attempt produced no diff",
                    exit_code=execution.exit_code,
                )
                notes.append("no changes produced")
                return FactoryRun(claim.task_id, "failed", None, tuple(notes), claim.attempt_token)

            commit_sha = self.worktrees.commit(
                worktree, "factory(" + claim.task_id + "): " + claim.title
            )
            gate_report = self.gates.run(worktree)
            self.ledger.record_receipt(
                claim.task_id,
                claim.attempt_token,
                "gates",
                {**gate_report.as_dict(), "round": round_index, "commit": commit_sha},
            )
            if gate_report.passed:
                break
            self.worktrees.reset_soft(worktree)
            feedback = (
                "\nPrevious round failed the repository gates; fix these before stopping:\n"
                + gate_report.summary()
            )
            notes.append("gates failed in round " + str(round_index))
        else:
            self.ledger.finish(
                claim.task_id,
                claim.attempt_token,
                "failed",
                error="gates failed: "
                + (gate_report.summary()[:400] if gate_report is not None else "unknown"),
                exit_code=None if execution is None else execution.exit_code,
            )
            return FactoryRun(claim.task_id, "failed", None, tuple(notes), claim.attempt_token)

        assert gate_report is not None
        self.ledger.start_verification(claim.task_id, claim.attempt_token)
        diff_text = self.worktrees.diff_against(worktree)
        pre_sha = diff_sha256(worktree)
        verdict = self.qa.review(
            objective=claim.objective,
            acceptance=claim.acceptance,
            diff=diff_text,
            gates=gate_report,
            worktree=worktree,
        )
        post_sha = diff_sha256(worktree)
        self.ledger.record_receipt(
            claim.task_id,
            claim.attempt_token,
            "qa",
            {**verdict.as_dict(), "pre_sha": pre_sha, "post_sha": post_sha},
        )
        if pre_sha != post_sha:
            self.ledger.finish(
                claim.task_id,
                claim.attempt_token,
                "blocked",
                error="independent QA mutated the worktree; verdict rejected",
            )
            notes.append("QA changed the worktree; verdict discarded")
            return FactoryRun(claim.task_id, "blocked", None, tuple(notes), claim.attempt_token)
        if not verdict.approved:
            self.ledger.finish(
                claim.task_id,
                claim.attempt_token,
                "blocked",
                error="independent QA rejected: "
                + ("; ".join(verdict.findings)[:600] or "no findings recorded"),
            )
            notes.append("independent QA rejected the change")
            return FactoryRun(claim.task_id, "blocked", None, tuple(notes), claim.attempt_token)

        return self._deliver(claim, worktree, branch, gate_report, verdict, notes)

    def _deliver(
        self,
        claim: Claim,
        worktree: Path,
        branch: str,
        gates: GateReport,
        verdict: QAVerdict,
        notes: list[str],
    ) -> FactoryRun:
        self._push(worktree, branch)
        if self.publisher is None:
            self.ledger.finish(
                claim.task_id,
                claim.attempt_token,
                "blocked",
                error="verified change has no publisher configured",
            )
            notes.append("change committed and pushed but no publisher is configured")
            return FactoryRun(claim.task_id, "blocked", None, tuple(notes), claim.attempt_token)
        pr = self.publisher.open_draft_pr(
            branch=branch,
            title="[DRAFT][FACTORY] " + claim.title,
            body=self._pr_body(claim, gates, verdict),
        )
        self.ledger.record_receipt(
            claim.task_id,
            claim.attempt_token,
            "delivery",
            {"pr_url": pr.url, "branch": branch},
        )
        self.ledger.finish(
            claim.task_id, claim.attempt_token, "delivered", pr_url=pr.url, exit_code=0
        )
        notes.append("draft PR opened")
        return FactoryRun(claim.task_id, "delivered", pr.url, tuple(notes), claim.attempt_token)

    @staticmethod
    def _push(worktree: Path, branch: str) -> None:
        proc = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise ExecutorError("git push failed: " + proc.stderr.strip()[:400])

    def _log_path(self, claim: Claim, round_index: int) -> Path:
        directory = self.log_dir / claim.task_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / (str(claim.epoch) + "-" + str(round_index) + ".ndjson")

    @staticmethod
    def _engineer_prompt(claim: Claim, feedback: str) -> str:
        return _ENGINEER_PROMPT.format(
            title=claim.title,
            objective=claim.objective,
            acceptance="\n".join("- " + item for item in claim.acceptance) or "- none declared",
            scope="\n".join("- " + item for item in claim.scope) or "- the whole repository",
            feedback=feedback,
        )

    @staticmethod
    def _pr_body(claim: Claim, gates: GateReport, verdict: QAVerdict) -> str:
        gate_lines = "\n".join(
            "- " + item.name + ": " + ("PASS" if item.passed else "FAIL")
            + " (exit=" + str(item.exit_code) + ")"
            for item in gates.results
        )
        evidence = "\n".join("- " + item for item in verdict.evidence) or "- (none recorded)"
        acceptance = "\n".join("- " + item for item in claim.acceptance)
        return (
            "Autonomous factory delivery for task " + claim.task_id
            + " (attempt epoch " + str(claim.epoch) + ").\n\n"
            "## Objective\n" + claim.objective + "\n\n"
            "## Acceptance\n" + acceptance + "\n\n"
            "## Deterministic gates\n" + gate_lines + "\n\n"
            "## Independent QA evidence\n" + evidence + "\n\n"
            "Draft only: no merge, no production change. Human review required.\n"
        )
