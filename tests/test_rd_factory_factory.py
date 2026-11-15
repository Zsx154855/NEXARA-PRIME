"""Factory loop: delivery, rejection, timeouts, zombie recovery, remote gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nexara_prime.rd_factory.executor import ExecResult, WorktreeManager
from nexara_prime.rd_factory.factory import RDFactory
from nexara_prime.rd_factory.ledger import TaskLedger
from nexara_prime.rd_factory.publisher import DraftPR
from nexara_prime.rd_factory.qa import DeterministicGates, GateCommand


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.name", "Factory Test", cwd=repo)
    _git("config", "user.email", "factory@test.local", cwd=repo)
    (repo / "README.md").write_text("baseline\n")
    (repo / "src").mkdir()
    (repo / "src" / "gate.py").write_text("def broken():\n    return 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_smoke.py").write_text("def test_smoke():\n    assert True\n")
    _git("add", "--", "README.md", "src/gate.py", "tests/test_smoke.py", cwd=repo)
    _git("commit", "-m", "baseline", cwd=repo)
    return repo


class FakeExecutor:
    def __init__(self, *, write: bool = True, timed_out: bool = False):
        self.write = write
        self.timed_out = timed_out
        self.calls = 0

    def execute(self, worktree: Path, prompt: str, log_path) -> ExecResult:
        self.calls += 1
        if self.write:
            target = worktree / "src" / "gate.py"
            target.write_text("def broken():\n    return 0\n")
        return ExecResult(
            exit_code=None if self.timed_out else 0,
            timed_out=self.timed_out,
            duration_s=0.5,
            log_path=str(log_path),
            events=3,
            diff_sha256="deadbeef",
            changed_files=["src/gate.py"] if self.write else [],
        )


class FakeQA:
    def __init__(self, approved: bool = True, mutate: bool = False, findings=()):
        self.approved = approved
        self.mutate = mutate
        self.findings = findings

    def review(self, *, objective, acceptance, diff, gates, worktree):
        from nexara_prime.rd_factory.qa import QAVerdict

        if self.mutate:
            (worktree / "qa_sneak.py").write_text("sneaky\n")
        return QAVerdict(self.approved, tuple(self.findings), ("pytest exit=0",), True, "")


class StubPublisher:
    def __init__(self):
        self.calls: list[dict] = []

    def open_draft_pr(self, *, branch: str, title: str, body: str) -> DraftPR:
        self.calls.append({"branch": branch, "title": title, "body": body})
        return DraftPR(url="https://example.invalid/pr/1", number=1, branch=branch)


def _factory(tmp_path: Path, *, executor=None, qa=None, publisher=None, ledger=None,
             require_remote: bool = False) -> RDFactory:
    repo = _repo(tmp_path)
    db = ledger if ledger is not None else TaskLedger(tmp_path / "factory.db")
    factory = RDFactory(
        ledger=db,
        executor=executor or FakeExecutor(),
        worktrees=WorktreeManager(repo, tmp_path / "worktrees", "main"),
        gates=DeterministicGates([GateCommand("ok", ("python3", "-c", "pass"), timeout_s=60)]),
        qa=qa or FakeQA(),
        repo=repo,
        publisher=publisher,
        log_dir=tmp_path / "logs",
        require_remote=require_remote,
    )
    factory._push = lambda worktree, branch: None  # type: ignore[method-assign]
    return factory


def _enqueue(ledger: TaskLedger) -> str:
    return ledger.enqueue(
        title="make gate return zero",
        objective="change broken() to return 0",
        acceptance=["src/gate.py returns 0"],
        scope=["src/gate.py"],
    )


def test_approved_change_is_delivered_as_draft_pr(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    publisher = StubPublisher()
    factory = _factory(tmp_path, publisher=publisher, ledger=ledger)
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None
    assert run.state == "delivered"
    assert run.pr_url == "https://example.invalid/pr/1"
    assert len(publisher.calls) == 1
    assert publisher.calls[0]["title"].startswith("[DRAFT][FACTORY]")

    kinds = [row["kind"] for row in ledger.receipts(task_id)]
    assert kinds == ["execution", "gates", "qa", "delivery"]
    view = ledger.get(task_id)
    assert view.state == "delivered"
    assert view.pr_url == "https://example.invalid/pr/1"
    ledger.close()


def test_rejected_change_is_blocked_and_never_published(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    publisher = StubPublisher()
    factory = _factory(
        tmp_path, qa=FakeQA(approved=False, findings=["does not satisfy acceptance"]),
        publisher=publisher, ledger=ledger,
    )
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None and run.state == "blocked"
    assert publisher.calls == []
    assert "QA rejected" in (ledger.get(task_id).last_error or "")
    ledger.close()


def test_qa_that_mutates_the_worktree_is_rejected(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    publisher = StubPublisher()
    factory = _factory(tmp_path, qa=FakeQA(mutate=True), publisher=publisher, ledger=ledger)
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None and run.state == "blocked"
    assert "mutated the worktree" in (ledger.get(task_id).last_error or "")
    assert publisher.calls == []
    ledger.close()


def test_no_diff_fails_the_attempt(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    factory = _factory(tmp_path, executor=FakeExecutor(write=False), ledger=ledger)
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None and run.state == "failed"
    assert ledger.get(task_id).last_error == "attempt produced no diff"
    ledger.close()


def test_timeout_releases_the_task_back_to_the_queue(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    factory = _factory(tmp_path, executor=FakeExecutor(timed_out=True), ledger=ledger)
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None and run.state == "queued"
    view = ledger.get(task_id)
    assert view.state == "queued"
    assert view.attempt_token is None
    assert view.epoch == 2
    ledger.close()


def test_require_remote_without_remote_refuses_to_run(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    factory = _factory(tmp_path, ledger=ledger, require_remote=True)
    task_id = _enqueue(ledger)

    run = factory.run_once()
    assert run is not None and run.state == "queued"
    assert ledger.get(task_id).last_error == "no authorized remote executor"
    ledger.close()


def test_status_reports_recovery_and_remote_policy(tmp_path: Path) -> None:
    ledger = TaskLedger(tmp_path / "factory.db")
    factory = _factory(tmp_path, ledger=ledger)
    status = factory.status()
    assert status["stats"]["queued"] == 0
    assert status["remote"]["mode"] == "fail-closed"
    assert status["remote"]["configured"] is False
    ledger.close()
