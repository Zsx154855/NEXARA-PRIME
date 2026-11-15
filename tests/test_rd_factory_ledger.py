"""Ledger invariants: mutual exclusion, fencing, zombie reaping, budgets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexara_prime.rd_factory.ledger import FenceError, LedgerError, TaskLedger


def _ledger(tmp_path: Path, name: str = "factory.db") -> TaskLedger:
    return TaskLedger(tmp_path / name)


def _enqueue(ledger: TaskLedger, **overrides) -> str:
    payload = {
        "title": "tighten gate",
        "objective": "make the gate reject empty diffs",
        "acceptance": ["gate exits nonzero on empty diff"],
        "scope": ["src"],
    }
    payload.update(overrides)
    return ledger.enqueue(**payload)


def test_claim_is_mutually_exclusive(tmp_path: Path) -> None:
    first = _ledger(tmp_path)
    second = _ledger(tmp_path)
    _enqueue(first)

    claim = first.claim("w1", ttl_seconds=900)
    assert claim is not None
    assert claim.attempts_used == 1
    assert second.claim("w2", ttl_seconds=900) is None

    first.close()
    second.close()


def test_stale_receipt_is_rejected(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    task_id = _enqueue(ledger)
    claim = ledger.claim("w1", ttl_seconds=900)
    assert claim is not None
    ledger.record_receipt(task_id, claim.attempt_token, "execution", {"exit_code": 0})
    ledger.release(task_id, claim.attempt_token, "retry")

    with pytest.raises(FenceError):
        ledger.record_receipt(task_id, claim.attempt_token, "execution", {"exit_code": 0})

    retry = ledger.claim("w1", ttl_seconds=900)
    assert retry is not None
    assert retry.attempt_token != claim.attempt_token
    assert retry.epoch > claim.epoch
    assert retry.attempts_used == claim.attempts_used + 1
    ledger.close()


def test_expired_lease_is_reaped_and_fenced(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    task_id = _enqueue(ledger)
    claim = ledger.claim("w1", ttl_seconds=0)
    assert claim is not None
    ledger.mark_running(task_id, claim.attempt_token, branch="factory/x")

    requeued = ledger.requeue_expired()
    assert requeued == [task_id]
    view = ledger.get(task_id)
    assert view.state == "queued"
    assert view.epoch == claim.epoch + 1
    assert [row["state"] for row in ledger.attempts(task_id)] == ["orphaned"]

    with pytest.raises(FenceError):
        ledger.finish(task_id, claim.attempt_token, "delivered")
    ledger.close()


def test_budget_exhaustion_stops_claiming(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    task_id = _enqueue(ledger, budget_attempts=1)
    claim = ledger.claim("w1", ttl_seconds=900)
    assert claim is not None
    ledger.release(task_id, claim.attempt_token, "retry")

    assert ledger.claim("w1", ttl_seconds=900) is None
    assert ledger.get(task_id).state == "queued"

    assert ledger.get(task_id).attempts_used == 1
    ledger.close()


def test_dedupe_key_returns_the_same_task(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    first = _enqueue(ledger, dedupe_key="gate-empty-diff")
    second = _enqueue(ledger, dedupe_key="gate-empty-diff")
    assert first == second
    assert len(ledger.list_tasks()) == 1
    ledger.close()


def _cancel_events(ledger: TaskLedger, task_id: str) -> list[dict]:
    return [event for event in ledger.events(task_id) if event["kind"] == "task.cancelled"]


def test_cancel_unknown_task_fails_closed(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    missing = "task_does_not_exist"

    with pytest.raises(LedgerError) as excinfo:
        ledger.cancel(missing, "typo")

    assert missing in str(excinfo.value)
    assert ledger.events(missing) == []
    ledger.close()


@pytest.mark.parametrize("terminal", ["delivered", "failed", "cancelled", "blocked"])
def test_cancel_terminal_task_is_rejected_and_state_preserved(tmp_path: Path, terminal: str) -> None:
    ledger = _ledger(tmp_path)
    task_id = _enqueue(ledger)
    claim = ledger.claim("w1", ttl_seconds=900)
    assert claim is not None
    if terminal == "cancelled":
        ledger.cancel(task_id, "first cancel")
    else:
        ledger.finish(task_id, claim.attempt_token, terminal)

    before = ledger.get(task_id)
    cancels_before = len(_cancel_events(ledger, task_id))

    with pytest.raises(LedgerError) as excinfo:
        ledger.cancel(task_id, "second cancel")

    after = ledger.get(task_id)
    assert task_id in str(excinfo.value)
    assert after.state == terminal
    assert after.last_error == before.last_error
    assert after.owner == before.owner
    assert after.epoch == before.epoch
    assert len(_cancel_events(ledger, task_id)) == cancels_before
    ledger.close()


@pytest.mark.parametrize("advance", ["queued", "running"])
def test_cancel_active_task_sets_cancelled_and_emits_one_event(tmp_path: Path, advance: str) -> None:
    ledger = _ledger(tmp_path)
    task_id = _enqueue(ledger)
    if advance == "running":
        claim = ledger.claim("w1", ttl_seconds=900)
        assert claim is not None
        ledger.mark_running(task_id, claim.attempt_token, branch="factory/x")

    ledger.cancel(task_id, "superseded")

    view = ledger.get(task_id)
    assert view.state == "cancelled"
    assert view.attempt_token is None
    assert view.owner is None
    assert view.lease_expires_at is None
    signals = _cancel_events(ledger, task_id)
    assert len(signals) == 1
    assert json.loads(signals[0]["detail"])["reason"] == "superseded"
    ledger.close()
