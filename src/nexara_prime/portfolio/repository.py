"""Portfolio repository — persistence for ProgramRecords and Portfolio state."""
from __future__ import annotations

from typing import Any

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.portfolio.models import (
    ProgramRecord,
    ProgramStatus,
    Portfolio,
    ProgramDecision,
    ProgramCheckpoint,
)
from nexara_prime.models import now_iso


class PortfolioRepository:
    """Persists and loads portfolio state from SQLiteStore."""

    RECORD_TYPE = "program_record"
    PORTFOLIO_TYPE = "portfolio_state"
    DECISION_TYPE = "program_decision"
    CHECKPOINT_TYPE = "program_checkpoint"

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._store = store
        self._events = events

    def save_program(self, program: ProgramRecord) -> None:
        program.updated_at = now_iso()
        payload = _program_to_dict(program)
        self._store.save_record(
            program.program_id, self.RECORD_TYPE, payload,
            program.created_at, program.program_id,
        )

    def load_program(self, program_id: str) -> ProgramRecord | None:
        raw = self._store.get_record(program_id)
        if not raw:
            return None
        return _dict_to_program(raw)

    def list_programs(self, status: ProgramStatus | None = None) -> list[ProgramRecord]:
        records = self._store.list_records(self.RECORD_TYPE)
        programs = []
        for raw in records:
            try:
                p = _dict_to_program(raw)
                if status is None or p.status == status:
                    programs.append(p)
            except Exception:
                continue
        return programs

    def save_portfolio(self, portfolio: Portfolio) -> None:
        portfolio.last_snapshot_at = now_iso()
        payload = _portfolio_to_dict(portfolio)
        self._store.save_record(
            portfolio.portfolio_id, self.PORTFOLIO_TYPE, payload,
            now_iso(), portfolio.portfolio_id,
        )

    def load_portfolio(self) -> Portfolio | None:
        raw = self._store.get_record("nexara_prime_portfolio_v1")
        if not raw:
            return None
        return _dict_to_portfolio(raw)

    def save_decision(self, decision: ProgramDecision) -> None:
        payload = {
            "decision_id": decision.decision_id,
            "program_id": decision.program_id,
            "reason": decision.reason,
            "priority_score": decision.priority_score,
            "selected_for_execution": decision.selected_for_execution,
            "alternatives_considered": decision.alternatives_considered,
            "created_at": decision.created_at,
        }
        self._store.save_record(
            decision.decision_id, self.DECISION_TYPE, payload,
            decision.created_at, decision.program_id,
        )
        self._events.publish(
            "portfolio.decision.recorded", decision.program_id,
            "portfolio", "portfolio_director", decision.decision_id,
            payload,
        )

    def save_checkpoint(self, checkpoint: ProgramCheckpoint) -> None:
        payload = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "program_id": checkpoint.program_id,
            "mission_id": checkpoint.mission_id,
            "phase": checkpoint.phase,
            "snapshot": checkpoint.snapshot,
            "created_at": checkpoint.created_at,
        }
        self._store.save_record(
            checkpoint.checkpoint_id, self.CHECKPOINT_TYPE, payload,
            checkpoint.created_at, checkpoint.program_id,
        )

    def list_decisions(self, program_id: str = "") -> list[dict[str, Any]]:
        records = self._store.list_records(self.DECISION_TYPE, program_id or None)
        return records


def _program_to_dict(p: ProgramRecord) -> dict[str, Any]:
    return {
        "program_id": p.program_id, "name": p.name, "purpose": p.purpose,
        "owner_goal_id": p.owner_goal_id, "status": p.status.value,
        "priority": p.priority,
        "value_score": p.value_score, "urgency_score": p.urgency_score,
        "risk_score": p.risk_score, "effort_score": p.effort_score,
        "confidence": p.confidence,
        "dependencies": [
            {"depends_on": d.depends_on, "dependency_type": d.dependency_type}
            for d in p.dependencies
        ],
        "blocked_by": p.blocked_by,
        "wait_conditions": [
            {
                "condition_id": w.condition_id,
                "condition_type": w.condition_type,
                "description": w.description,
                "external_ref": w.external_ref,
                "check_interval_seconds": w.check_interval_seconds,
                "satisfied": w.satisfied,
                "timeout_seconds": w.timeout_seconds,
            }
            for w in p.wait_conditions
        ],
        "active_missions": p.active_missions,
        "completed_missions": p.completed_missions,
        "milestones": [
            {"milestone_id": m.milestone_id, "name": m.name, "reached": m.reached}
            for m in p.milestones
        ],
        "worker_requirements": p.worker_requirements,
        "budget": {
            "token_budget": p.budget.token_budget,
            "cost_budget": p.budget.cost_budget,
            "time_budget_hours": p.budget.time_budget_hours,
            "retry_budget": p.budget.retry_budget,
            "tokens_used": p.budget.tokens_used,
            "cost_used": p.budget.cost_used,
            "time_used_hours": p.budget.time_used_hours,
            "retries_used": p.budget.retries_used,
        },
        "review_budget": {
            "max_cycles": p.review_budget.max_cycles,
            "max_elapsed_time_hours": p.review_budget.max_elapsed_time_hours,
            "cycles_used": p.review_budget.cycles_used,
            "root_cause_counts": p.review_budget.root_cause_counts,
        },
        "checkpoint_ref": p.checkpoint_ref,
        "evidence_refs": p.evidence_refs,
        "created_at": p.created_at, "updated_at": p.updated_at,
        "started_at": p.started_at, "completed_at": p.completed_at,
        "next_action": p.next_action, "next_review_at": p.next_review_at,
        "metadata": p.metadata,
    }


def _dict_to_program(d: dict[str, Any]) -> ProgramRecord:
    from nexara_prime.portfolio.models import (
        ProgramDependency, ProgramBudget, ReviewBudget,
        ProgramWaitCondition, ProgramMilestone,
    )
    raw = d.get("payload", d)
    deps = []
    for dep in raw.get("dependencies", []):
        deps.append(ProgramDependency(
            depends_on=dep.get("depends_on", ""),
            dependency_type=dep.get("dependency_type", "hard"),
        ))
    budget_raw = raw.get("budget", {})
    budget = ProgramBudget(
        token_budget=budget_raw.get("token_budget", 0),
        cost_budget=budget_raw.get("cost_budget", 0),
        time_budget_hours=budget_raw.get("time_budget_hours", 0),
        retry_budget=budget_raw.get("retry_budget", 3),
        tokens_used=budget_raw.get("tokens_used", 0),
        cost_used=budget_raw.get("cost_used", 0),
        time_used_hours=budget_raw.get("time_used_hours", 0),
        retries_used=budget_raw.get("retries_used", 0),
    )
    rb_raw = raw.get("review_budget", {})
    review_budget = ReviewBudget(
        program_id=raw.get("program_id", ""),
        max_cycles=rb_raw.get("max_cycles", 10),
        max_elapsed_time_hours=rb_raw.get("max_elapsed_time_hours", 48.0),
        cycles_used=rb_raw.get("cycles_used", 0),
        root_cause_counts=rb_raw.get("root_cause_counts", {}),
    )
    waits = []
    for w in raw.get("wait_conditions", []):
        waits.append(ProgramWaitCondition(
            condition_id=w.get("condition_id", ""),
            condition_type=w.get("condition_type", ""),
            description=w.get("description", ""),
            external_ref=w.get("external_ref", ""),
            satisfied=w.get("satisfied", False),
        ))
    milestones = []
    for m in raw.get("milestones", []):
        milestones.append(ProgramMilestone(
            milestone_id=m.get("milestone_id", ""),
            name=m.get("name", ""),
            reached=m.get("reached", False),
        ))
    return ProgramRecord(
        program_id=raw.get("program_id", ""),
        name=raw.get("name", ""),
        purpose=raw.get("purpose", ""),
        owner_goal_id=raw.get("owner_goal_id", ""),
        status=ProgramStatus(raw.get("status", "planned")),
        priority=raw.get("priority", 5),
        value_score=raw.get("value_score", 5.0),
        urgency_score=raw.get("urgency_score", 5.0),
        risk_score=raw.get("risk_score", 3.0),
        effort_score=raw.get("effort_score", 3.0),
        confidence=raw.get("confidence", 0.7),
        dependencies=deps,
        blocked_by=raw.get("blocked_by", []),
        wait_conditions=waits,
        active_missions=raw.get("active_missions", []),
        completed_missions=raw.get("completed_missions", []),
        milestones=milestones,
        worker_requirements=raw.get("worker_requirements", []),
        budget=budget,
        review_budget=review_budget,
        checkpoint_ref=raw.get("checkpoint_ref", ""),
        evidence_refs=raw.get("evidence_refs", []),
        created_at=raw.get("created_at", ""),
        updated_at=raw.get("updated_at", ""),
        started_at=raw.get("started_at", ""),
        completed_at=raw.get("completed_at", ""),
        next_action=raw.get("next_action", ""),
        next_review_at=raw.get("next_review_at", ""),
        metadata=raw.get("metadata", {}),
    )


def _portfolio_to_dict(p: Portfolio) -> dict[str, Any]:
    return {
        "portfolio_id": p.portfolio_id,
        "active_program_id": p.active_program_id,
        "owner_goals": p.owner_goals,
        "version": p.version,
        "program_ids": list(p.programs.keys()),
    }


def _dict_to_portfolio(d: dict[str, Any]) -> Portfolio:
    raw = d.get("payload", d)
    return Portfolio(
        portfolio_id=raw.get("portfolio_id", "nexara_prime_portfolio_v1"),
        active_program_id=raw.get("active_program_id", ""),
        owner_goals=raw.get("owner_goals", {}),
        version=raw.get("version", 1),
    )
