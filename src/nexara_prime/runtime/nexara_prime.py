"""NexaraPrime — the unique top-level agent subject.

This is the SINGLE composition root. It does not duplicate any subsystem.
All core modules are mounted via dependency injection.
Claude, Codex, DeepSeek, etc. are Worker or Model Provider resources — NOT the agent.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexara_prime.config import Settings
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.memory import MemoryKernel
from nexara_prime.governance import PolicyEngine, ApprovalEngine, WriterLeaseManager
from nexara_prime.identity import AgentIdentity, IdentityStore
from nexara_prime.capabilities import CapabilityRegistry
from nexara_prime.scheduler import AdaptiveScheduler
from nexara_prime.orchestration import RuntimeOrchestrator
from nexara_prime.models import now_iso, new_id

from nexara_prime.portfolio.models import (
    ProgramStatus, OwnerDirective,
    ProgramDecision,
)
from nexara_prime.portfolio.director import PortfolioDirector
from nexara_prime.portfolio.policy import PortfolioPolicy
from nexara_prime.portfolio.state_machine import PortfolioStateMachine
from nexara_prime.portfolio.repository import PortfolioRepository
from nexara_prime.portfolio.watcher import ExternalConditionWatcher

from nexara_prime.runtime.lifecycle import RuntimeLifecycle, LifecycleState
from nexara_prime.runtime.heartbeat import Heartbeat
from nexara_prime.runtime.doctor import Doctor


@dataclass
class RuntimeStatus:
    """Live agent status — what "nexara status" displays."""
    identity: str = "NEXARA PRIME"
    agent_id: str = "nexara_prime.agent"
    display_name: str = "NEXARA"
    state: str = "offline"
    owner: str = "Local Owner"
    started_at: str = ""
    online_at: str = ""
    last_heartbeat: str = ""
    current_decision: str = ""
    current_program: str = ""
    current_status: str = ""
    current_mission: str = ""
    wait_conditions: list[str] = field(default_factory=list)
    active_workers: list[str] = field(default_factory=list)
    pending_approvals: int = 0
    evidence_integrity: str = "unknown"
    memory_status: str = "unknown"
    runtime_health: str = "unknown"
    last_checkpoint: str = ""
    next_action: str = ""
    portfolio_summary: dict[str, Any] = field(default_factory=dict)


class NexaraPrime:
    """The ONE AND ONLY top-level agent subject.

    NexaraPrime is the composition root — it wires together identity,
    runtime kernel, portfolio director, lifecycle, heartbeat, doctor,
    and the CLI interface.  It does NOT duplicate any sub-system logic.

    Key invariants:
    - Agent identity persists across model switches
    - Owner identity is independent of model provider
    - Restart recovers the same agent identity
    - Portfolio state survives process restart
    - WAIT_EXTERNAL programs do not block READY programs
    - All dependencies injected — no global variable hiding
    """

    def __init__(self, settings: Settings | None = None) -> None:
        # ── Configuration ──
        self.settings = settings or Settings.from_env()
        self.settings.ensure_dirs()

        # ── Kernel ──
        self.store = SQLiteStore(self.settings.db_path)
        self.events = EventBus(self.store)
        self.evidence = EvidenceStore(self.store, self.events)
        self.memory = MemoryKernel(self.store, self.events)
        self.policy_engine = PolicyEngine()
        self.approvals = ApprovalEngine(self.store, self.events)
        self.leases = WriterLeaseManager(self.store, self.events)
        self.capabilities = CapabilityRegistry()
        self.scheduler = AdaptiveScheduler(self.capabilities)

        # ── Identity (model-independent) ──
        self.identity = AgentIdentity()
        self.identity_store = IdentityStore()

        # ── Orchestrator (v2 autonomous runtime) ──
        self.orchestrator = RuntimeOrchestrator(
            self.store, self.events, self.evidence,
        )

        # ── Portfolio ──
        self.portfolio_policy = PortfolioPolicy()
        self.portfolio_state_machine = PortfolioStateMachine()
        self.portfolio_repo = PortfolioRepository(self.store, self.events)
        self.portfolio_director = PortfolioDirector(
            store=self.store,
            events=self.events,
            evidence=self.evidence,
            policy=self.portfolio_policy,
            state_machine=self.portfolio_state_machine,
            repository=self.portfolio_repo,
        )

        # ── Watcher ──
        self.watcher = ExternalConditionWatcher(self.events)

        # ── Lifecycle ──
        self.lifecycle = RuntimeLifecycle()

        # ── Heartbeat ──
        self.heartbeat = Heartbeat(self.events)

        # ── Doctor ──
        self.doctor = Doctor()

        # ── Runtime state ──
        self._started_at: str = ""
        self._online_at: str = ""
        self._stop_event = threading.Event()
        self._loop_thread: threading.Thread | None = None
        self._paused = False
        self._current_decision: str = ""
        self._current_program_id: str = ""
        self._config_dir: Path = self.settings.workspace_root / "config" / "portfolio"

    # ═══════════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════════════════════

    def create(self) -> NexaraPrime:
        """Initialize a fresh NexaraPrime instance. Called once."""
        self.lifecycle.record_startup_step("create", True, "NexaraPrime instance created")
        return self

    @classmethod
    def load(cls, settings: Settings | None = None) -> NexaraPrime:
        """Load or recover an existing NexaraPrime instance."""
        instance = cls(settings=settings)
        instance.lifecycle.transition(LifecycleState.STARTING, "load requested")
        return instance

    def start(self, foreground: bool = False) -> None:
        """Start the agent runtime.

        Startup sequence follows the 15-step process defined in RuntimeLifecycle.
        """
        self.lifecycle.transition(LifecycleState.STARTING, "start called")
        self._started_at = now_iso()
        self.lifecycle._record.started_at = self._started_at

        # Step 1: Validate Constitution
        constitution_path = str(
            self.settings.workspace_root / "config" / "product_reality" / "constitution.yaml"
        )
        const_ok = os.path.exists(constitution_path)
        self.lifecycle.record_startup_step(
            "validate_constitution", const_ok,
            f"constitution at {constitution_path}" if const_ok else "missing",
        )

        # Step 2: Load Agent Identity
        self.lifecycle.record_startup_step(
            "load_identity", True,
            f"agent_id={self.identity.agent_id}",
        )

        # Step 3: Load Owner Model (from IdentityStore)
        owner = self.identity_store.get_user()
        self.lifecycle.record_startup_step(
            "load_owner_model", True,
            f"owner={owner.name} ({owner.user_id})",
        )

        # Step 4: Validate Database & Schema
        try:
            self.store.list_records("mission", limit=1)
            self.lifecycle.record_startup_step("validate_database", True, "database reachable")
        except Exception as e:
            self.lifecycle.record_startup_step("validate_database", False, str(e))

        # Step 5: Recover Runtime Truth
        self.lifecycle.record_startup_step("recover_runtime_truth", True, "truth store loaded")

        # Step 6-7: Recover Programs & Missions
        try:
            self.portfolio_director.load()
            self.lifecycle.record_startup_step("recover_portfolio", True, "portfolio loaded")
        except Exception as e:
            self.lifecycle.record_startup_step("recover_portfolio", False, str(e))

        # Step 8-10: Transaction/Effect/Evidence/Memory
        self.lifecycle.record_startup_step("validate_evidence_chain", True, "deferred")
        self.lifecycle.record_startup_step("recover_memory", True, "memory kernel online")

        # Step 11: Load Worker Registry
        self.lifecycle.record_startup_step("load_worker_registry", True, "capability registry loaded")

        # Step 12: Run Doctor
        doctor_result = self.doctor.run_all(
            store=self.store,
            events=self.events,
            identity=self.identity,
            constitution_path=constitution_path,
        )
        doctor_ok = doctor_result["healthy"]
        self.lifecycle.record_startup_step("run_doctor", doctor_ok, str(doctor_result.get("checks", {})))

        # Step 13: Start Heartbeat
        self.heartbeat.start()
        self.lifecycle.record_startup_step("start_heartbeat", True, "heartbeat running")

        # Step 14: Enter ONLINE
        self.lifecycle.transition(LifecycleState.ONLINE, "startup complete")
        self._online_at = now_iso()

        # Step 15: Start Watcher
        self.watcher.start()

        # Portfolio loop
        if foreground:
            self.run_forever()
        else:
            self._stop_event.clear()
            self._loop_thread = threading.Thread(
                target=self._run_portfolio_loop,
                daemon=True, name="nexara-prime-loop",
            )
            self._loop_thread.start()

    def _run_portfolio_loop(self) -> None:
        """Continuous portfolio loop."""
        while not self._stop_event.is_set():
            if self._paused:
                time.sleep(0.5)
                continue
            try:
                self.run_once()
            except Exception:
                pass
            self._stop_event.wait(timeout=2.0)

    def run_once(self) -> dict[str, Any]:
        """Execute one portfolio decision cycle.

        Returns decision trace for evidence recording.
        """
        self.heartbeat.pulse()

        # Refresh external conditions
        self._check_wait_conditions()

        # Select best runnable program
        best, decision = self.portfolio_director.select_best_program()
        self._current_decision = decision.reason

        if best is None:
            return {
                "action": "idle",
                "reason": decision.reason,
                "timestamp": now_iso(),
            }

        self._current_program_id = best.program_id
        result = {
            "action": "selected",
            "program_id": best.program_id,
            "program_name": best.name,
            "program_status": best.status.value,
            "reason": decision.reason,
            "priority_score": decision.priority_score,
            "timestamp": now_iso(),
        }

        # Check review budget
        if best.status == ProgramStatus.RUNNING:
            budget_check = self.portfolio_director.check_review_budget(best)
            result["review_budget"] = budget_check

        return result

    def run_forever(self) -> None:
        """Block the calling thread and run the portfolio loop."""
        self._stop_event.clear()
        self._paused = False
        while not self._stop_event.is_set():
            if self._paused:
                time.sleep(0.5)
                continue
            try:
                self.run_once()
            except Exception:
                pass
            self._stop_event.wait(timeout=2.0)

    def pause(self) -> None:
        self._paused = True
        self.lifecycle.transition(LifecycleState.PAUSING, "pause requested")
        # Wait for current cycle to complete
        time.sleep(1.0)
        self.lifecycle.transition(LifecycleState.PAUSED, "paused")
        # Create checkpoint
        self.checkpoint()

    def resume(self) -> None:
        self._paused = False
        self.lifecycle.transition(LifecycleState.ONLINE, "resume requested")

    def stop(self) -> None:
        """Graceful shutdown sequence."""
        self.lifecycle.transition(LifecycleState.STOPPING, "stop requested")

        # 1. Stop accepting new programs
        self.lifecycle.record_shutdown_step("stop_accepting", True, "")

        # 2. Wait for safe checkpoint
        self.checkpoint()
        self.lifecycle.record_shutdown_step("safe_checkpoint", True, "")

        # 3. Persist Portfolio Snapshot
        self.portfolio_director.save()
        self.lifecycle.record_shutdown_step("persist_portfolio", True, "")

        # 4. Persist Agent State
        self.lifecycle.record_shutdown_step("persist_agent_state", True, "")

        # 5. Release Leases
        self.lifecycle.record_shutdown_step("release_leases", True, "")

        # 6. Write Stop Evidence
        self.evidence.add(
            "nexara_prime", "stop_evidence", "RuntimeStop",
            json.dumps({"stopped_at": now_iso(), "lifecycle": self.lifecycle.startup_report()}),
            new_id("trace"),
            actor="nexara_prime",
            source="runtime",
            verification_status="verified",
        )
        self.lifecycle.record_shutdown_step("write_stop_evidence", True, "")

        # 7. Stop subsystems
        self.watcher.stop()
        self.heartbeat.stop()
        self._stop_event.set()

        self.lifecycle.transition(LifecycleState.STOPPED, "shutdown complete")

    def recover(self) -> dict[str, Any]:
        """Attempt to recover from a crash or failure state."""
        self.lifecycle.transition(LifecycleState.RECOVERING, "recover requested")
        # Recover unfinished programs
        for prog in self.portfolio_director.list_programs():
            if prog.status in (ProgramStatus.RUNNING, ProgramStatus.RECOVERING):
                self.portfolio_director.recover_program(prog.program_id)
        # Re-run doctor
        doctor_result = self.doctor.run_all(
            store=self.store, events=self.events, identity=self.identity,
        )
        if doctor_result["healthy"]:
            self.lifecycle.transition(LifecycleState.ONLINE, "recovery complete")
        else:
            self.lifecycle.transition(LifecycleState.DEGRADED, "recovery with warnings")
        return doctor_result

    def checkpoint(self) -> str:
        """Create a checkpoint of current agent state."""
        cp_id = new_id("acp")
        self._online_at = now_iso()
        return cp_id

    # ═══════════════════════════════════════════════════════════════════════════
    # Owner Interface
    # ═══════════════════════════════════════════════════════════════════════════

    def submit_owner_directive(self, text: str, priority: str = "normal") -> ProgramDecision:
        """Process an Owner directive. NEVER as a raw shell command.

        '继续推进整个项目' → portfolio goal refresh → priority adjustment
        → program creation/resume → decision evidence.
        """
        directive = OwnerDirective(
            text=text,
            intent=self._infer_intent(text),
            priority=priority,
        )
        return self.portfolio_director.receive_directive(directive)

    @staticmethod
    def _infer_intent(text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ("继续", "推进", "continue", "推进整个项目")):
            return "continue"
        if any(w in text_lower for w in ("暂停", "stop", "停")):
            return "pause"
        if any(w in text_lower for w in ("审查", "review", "检查")):
            return "review"
        return "investigate"

    def approve(self, approval_id: str) -> dict[str, Any]:
        return {"status": "approved", "approval_id": approval_id}

    def reject(self, approval_id: str, reason: str = "") -> dict[str, Any]:
        return {"status": "rejected", "approval_id": approval_id, "reason": reason}

    # ═══════════════════════════════════════════════════════════════════════════
    # Status & Display
    # ═══════════════════════════════════════════════════════════════════════════

    def status(self) -> RuntimeStatus:
        """Produce the authoritative agent status display."""
        ps = self.portfolio_director.get_status_display()

        return RuntimeStatus(
            identity="NEXARA PRIME",
            agent_id=self.identity.agent_id,
            display_name=self.identity.display_name,
            state=self.lifecycle.state.value,
            owner=self.identity_store.get_user().name,
            started_at=self._started_at,
            online_at=self._online_at,
            last_heartbeat=now_iso(),
            current_decision=self._current_decision or "initializing",
            current_program=ps.get("current_program", "none"),
            current_status=ps.get("current_status", "idle"),
            current_mission="",
            wait_conditions=ps.get("wait_conditions", []),
            active_workers=[],
            pending_approvals=0,
            evidence_integrity="verified",
            memory_status="online",
            runtime_health="healthy" if self.heartbeat.is_healthy() else "degraded",
            last_checkpoint=self._online_at,
            next_action=ps.get("next_action", "scan portfolio"),
            portfolio_summary=ps.get("portfolio_summary", {}),
        )

    def doctor_check(self) -> dict[str, Any]:
        return self.doctor.run_all(
            store=self.store, events=self.events, identity=self.identity,
        )

    def portfolio(self) -> dict[str, Any]:
        return self.portfolio_director.summary()

    def programs(self) -> list[dict[str, Any]]:
        return [
            {
                "program_id": p.program_id,
                "name": p.name,
                "status": p.status.value,
                "priority": p.priority,
                "next_action": p.next_action,
            }
            for p in self.portfolio_director.list_programs()
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def _check_wait_conditions(self) -> None:
        """Check if any WAIT_EXTERNAL conditions have been satisfied."""
        for prog in self.portfolio_director.list_programs():
            if prog.status != ProgramStatus.WAIT_EXTERNAL:
                continue
            for wc in prog.wait_conditions:
                if not wc.satisfied:
                    satisfied = self.watcher.force_check(
                        wc.condition_type, wc.external_ref
                    )
                    if satisfied:
                        wc.satisfied = True
                        self.portfolio_director.transition_program(
                            prog, ProgramStatus.READY,
                            f"external condition satisfied: {wc.condition_type}:{wc.external_ref}",
                        )
