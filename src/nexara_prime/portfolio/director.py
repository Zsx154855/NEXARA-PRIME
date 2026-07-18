"""Portfolio Director — selects and manages programs across the portfolio."""
from __future__ import annotations

import threading
from typing import Any

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.portfolio.models import (
    ProgramRecord,
    ProgramStatus,
    ProgramDecision,
    ProgramCheckpoint,
    Portfolio,
    OwnerDirective,
)
from nexara_prime.portfolio.state_machine import PortfolioStateMachine
from nexara_prime.portfolio.policy import PortfolioPolicy
from nexara_prime.portfolio.repository import PortfolioRepository
from nexara_prime.models import now_iso, new_id


class PortfolioDirector:
    """Portfolio Operating System — Owner → Programs → Agent Mind → Mission.

    Responsibilities:
    - Receive Owner long-term goals
    - Maintain Program Portfolio with priorities, dependencies, budgets
    - Select the most valuable runnable program
    - Prevent single-program resource monopolization
    - Manage WAIT_EXTERNAL without blocking other READY programs
    - Create checkpoints, recover interrupted programs, archive completed ones

    PortfolioDirector only SELECTS programs and CREATES/RESUMES missions.
    It NEVER directly executes effects.
    """

    def __init__(
        self,
        store: SQLiteStore,
        events: EventBus,
        evidence: EvidenceStore,
        policy: PortfolioPolicy | None = None,
        state_machine: PortfolioStateMachine | None = None,
        repository: PortfolioRepository | None = None,
    ) -> None:
        self._store = store
        self._events = events
        self._evidence = evidence
        self.policy = policy or PortfolioPolicy()
        self.state_machine = state_machine or PortfolioStateMachine()
        self.repository = repository or PortfolioRepository(store, events)

        self._portfolio: Portfolio = Portfolio()
        self._decision_history: list[ProgramDecision] = []
        self._lock = threading.RLock()
        self._started_at: str = ""

    # ── Lifecycle ──

    def load(self) -> Portfolio:
        """Load or initialize the portfolio."""
        saved = self.repository.load_portfolio()
        if saved:
            self._portfolio = saved
            # Load all programs
            for prog_id in saved.programs if hasattr(saved, 'programs') else []:
                prog = self.repository.load_program(prog_id)
                if prog:
                    self._portfolio.programs[prog_id] = prog
        else:
            self._portfolio = Portfolio()
        return self._portfolio

    def save(self) -> None:
        for prog in self._portfolio.programs.values():
            self.repository.save_program(prog)
        self.repository.save_portfolio(self._portfolio)

    # ── Portfolio Operations ──

    def add_program(self, program: ProgramRecord) -> None:
        with self._lock:
            self._portfolio.programs[program.program_id] = program
            self.repository.save_program(program)

    def get_program(self, program_id: str) -> ProgramRecord | None:
        return self._portfolio.programs.get(program_id)

    def list_programs(
        self, status: ProgramStatus | None = None
    ) -> list[ProgramRecord]:
        progs = list(self._portfolio.programs.values())
        if status:
            progs = [p for p in progs if p.status == status]
        return sorted(progs, key=lambda p: p.priority, reverse=True)

    def list_runnable(self) -> list[ProgramRecord]:
        """Programs that can be executed now."""
        runnable_statuses = {
            ProgramStatus.READY,
            ProgramStatus.RUNNING,
            ProgramStatus.RECOVERING,
        }
        return [
            p for p in self._portfolio.programs.values()
            if p.status in runnable_statuses
            and not p.blocked_by
        ]

    # ── Decision Engine ──

    def select_best_program(self) -> tuple[ProgramRecord | None, ProgramDecision]:
        """Select the highest-value runnable program.

        WAIT_EXTERNAL programs are NOT selected — they're bypassed for
        independent READY programs.  This is the core non-blocking behavior.
        """
        with self._lock:
            runnable = self.list_runnable()
            if not runnable:
                decision = ProgramDecision(
                    program_id="", reason="no_runnable_programs",
                    priority_score=0.0, selected_for_execution=False,
                )
                self._decision_history.append(decision)
                self.repository.save_decision(decision)
                return None, decision

            # Score all candidates
            scored = []
            for prog in runnable:
                score = self.policy.score_program(prog)
                scored.append((prog, score))

            scored.sort(key=lambda x: x[1].value, reverse=True)

            best_prog, best_score = scored[0]

            alternatives = [
                f"{p.program_id}({s.value:.1f})"
                for p, s in scored[1:4]
            ]

            decision = ProgramDecision(
                program_id=best_prog.program_id,
                reason=f"Selected highest priority: {best_score.value:.1f} "
                       f"(value={best_score.value_component:.1f} "
                       f"urgency={best_score.urgency_component:.1f} "
                       f"owner_priority={best_score.owner_priority_component:.1f})",
                priority_score=best_score.value,
                selected_for_execution=True,
                alternatives_considered=alternatives,
            )
            self._decision_history.append(decision)
            self.repository.save_decision(decision)

            self._portfolio.active_program_id = best_prog.program_id

            # Emit evidence of the decision
            self._evidence.add(
                best_prog.program_id, "portfolio_decision",
                "PortfolioDecision",
                f"Selected program '{best_prog.name}' "
                f"(score={best_score.value:.1f}) over alternatives: {alternatives}",
                decision.decision_id,
                actor="portfolio_director",
                source="portfolio_policy",
                verification_status="verified",
            )

            return best_prog, decision

    # ── Owner Directive Handling ──

    def receive_directive(self, directive: OwnerDirective) -> ProgramDecision:
        """Process an Owner directive — NEVER as a raw shell command.

        '继续推进整个项目' becomes: portfolio goal refresh → priority adjustment
        → program creation or resume → decision evidence.
        """
        with self._lock:
            self._portfolio.directives.append(directive)

            # Apply directive to all relevant programs
            for prog in self._portfolio.programs.values():
                if directive.scope == "*" or directive.scope == prog.program_id:
                    _ = self.policy.apply_owner_directive(prog, directive)
                    if directive.priority == "urgent":
                        prog.priority = min(10, prog.priority + 3)
                    elif directive.priority == "high":
                        prog.priority = min(10, prog.priority + 2)
                    else:
                        prog.priority = min(10, prog.priority + 1)

            directive.status = "processed"

            return self.select_best_program()[1]

    # ── State Transitions ──

    def transition_program(
        self, program: ProgramRecord, target: ProgramStatus, reason: str = ""
    ) -> ProgramRecord:
        """Transition a program to a new status with decision recording."""
        with self._lock:
            decision = ProgramDecision(
                program_id=program.program_id,
                reason=reason or f"transition: {program.status.value} → {target.value}",
                priority_score=0.0,
            )
            self.state_machine.transition(program, target, decision)
            self.repository.save_program(program)
            self.repository.save_decision(decision)

            program.updated_at = now_iso()
            if target == ProgramStatus.RUNNING and not program.started_at:
                program.started_at = now_iso()
            if target == ProgramStatus.COMPLETED:
                program.completed_at = now_iso()

            self._events.publish(
                "portfolio.program.transitioned",
                program.program_id, "portfolio", "portfolio_director",
                decision.decision_id,
                {
                    "from_status": str(program.status.value),
                    "to_status": target.value,
                    "reason": reason,
                },
            )
            return program

    # ── Checkpoint / Recovery ──

    def checkpoint(self, program: ProgramRecord, mission_id: str = "", phase: str = "") -> ProgramCheckpoint:
        snapshot = {
            "status": program.status.value,
            "active_missions": list(program.active_missions),
            "completed_missions": list(program.completed_missions),
            "budget_used": {
                "tokens": program.budget.tokens_used,
                "cost": program.budget.cost_used,
                "retries": program.budget.retries_used,
            },
        }
        cp = ProgramCheckpoint(
            program_id=program.program_id,
            mission_id=mission_id,
            phase=phase,
            snapshot=snapshot,
        )
        self.repository.save_checkpoint(cp)
        program.checkpoint_ref = cp.checkpoint_id
        return cp

    def recover_program(self, program_id: str) -> ProgramRecord | None:
        """Attempt to recover a program from its last checkpoint."""
        prog = self._portfolio.programs.get(program_id)
        if not prog:
            return None
        if prog.status == ProgramStatus.FAILED:
            self.transition_program(prog, ProgramStatus.RECOVERING, "crash recovery initiated")
        return prog

    # ── Review Budget ──

    def check_review_budget(self, program: ProgramRecord) -> dict[str, Any]:
        result = self.policy.evaluate_review_budget(program)
        if result["action"] == "merge_readiness":
            self.transition_program(
                program, ProgramStatus.COMPLETED,
                f"Review budget exhausted ({program.review_budget.cycles_used}/{program.review_budget.max_cycles}) — entering merge readiness",
            )
        elif result["action"] == "structural_fix_required":
            self._evidence.add(
                program.program_id, "structural_fix_required",
                "PortfolioPolicy",
                f"Root cause repeated {program.review_budget.repeated_root_cause_limit}+ times — structural fix required. "
                f"Root causes: {program.review_budget.root_cause_counts}",
                new_id("trace"),
                actor="portfolio_director",
                source="portfolio_policy",
                verification_status="verified",
            )
        return result

    # ── Portfolio Summary ──

    def summary(self) -> dict[str, Any]:
        """Produce a human-readable portfolio summary."""
        with self._lock:
            programs = []
            for prog in sorted(
                self._portfolio.programs.values(),
                key=lambda p: (p.priority, p.value_score),
                reverse=True,
            ):
                programs.append({
                    "program_id": prog.program_id,
                    "name": prog.name,
                    "status": prog.status.value,
                    "priority": prog.priority,
                    "value_score": prog.value_score,
                    "active_missions": len(prog.active_missions),
                    "completed_missions": len(prog.completed_missions),
                    "next_action": prog.next_action,
                    "wait_conditions": [
                        w.condition_type for w in prog.wait_conditions if not w.satisfied
                    ],
                })

            return {
                "portfolio_id": self._portfolio.portfolio_id,
                "active_program_id": self._portfolio.active_program_id,
                "total_programs": len(self._portfolio.programs),
                "programs": programs,
                "owner_goals": self._portfolio.owner_goals,
                "pending_directives": len([
                    d for d in self._portfolio.directives if d.status == "active"
                ]),
                "last_decision": (
                    self._decision_history[-1].reason if self._decision_history else "none"
                ),
            }

    def get_status_display(self) -> dict[str, Any]:
        """Structured status for CLI display."""
        s = self.summary()
        active = self._portfolio.programs.get(self._portfolio.active_program_id)

        wait_conditions = []
        if active:
            wait_conditions = [
                f"{w.condition_type}:{w.external_ref}"
                for w in active.wait_conditions if not w.satisfied
            ]

        return {
            "current_program": active.name if active else "none",
            "current_status": active.status.value if active else "idle",
            "current_decision": (
                self._decision_history[-1].reason if self._decision_history else "initializing"
            ),
            "wait_conditions": wait_conditions,
            "next_action": active.next_action if active else "scan portfolio",
            "portfolio_summary": s,
        }
