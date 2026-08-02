"""Sovereign Execution Coordinator — Phase C product integration layer.

Bridges Phase A+B brain modules (governance, compiler, durable runtime)
into NexaraRuntime's product API, establishing a single source of truth
for mission execution, approval, authorization, and human control.

Architecture:
  NexaraRuntime API
       │
       ▼
  SovereignExecutionCoordinator  ←── this module
       │
       ├── AutonomousGovernance (R0-R4 fail-closed)
       ├── MissionCompiler (intent → contract)
       ├── StateManager (durable SQLite checkpoint)
       ├── NexaraRuntime.mission_compiler.run() / plan() etc.
       └── Human Control State Machine

Single Sources of Truth:
  MISSION_SOT:     NexaraRuntime.mission_manager + SQLiteStore
  APPROVAL_SOT:    AutonomousGovernance.ApprovalOrchestrator
  AUTHORIZATION_SOT: PolicyRuntime.enforce() / verify()
  CHECKPOINT_SOT:  StateManager (SQLite WAL)
  EVIDENCE_SOT:    EvidenceStore + EventBus
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .brain.governance.autonomous_governance import (
    ApprovalLevel, ApprovalOrchestrator, AuthorityEngine,
    PolicyRuntime, RISK_APPROVAL_MAP, REQUIRES_APPROVAL,
)
from .brain.mission_compiler import MissionCompiler as BrainMissionCompiler
from .brain.runtime.persistent_runtime import Checkpoint, RecoveryEngine, StateManager
from .models import RiskLevel, now_iso, new_id


class ControlState(str, Enum):
    AUTONOMOUS = "autonomous"
    PAUSE_REQUESTED = "pause_requested"
    PAUSED = "paused"
    TAKEOVER_REQUESTED = "takeover_requested"
    HUMAN_CONTROLLED = "human_controlled"
    RELEASE_REQUESTED = "release_requested"


class ControlAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    TAKEOVER = "takeover"
    RELEASE_TAKEOVER = "release_takeover"
    APPROVE = "approve"
    REJECT = "reject"
    REVOKE = "revoke_approval"
    RECOVER = "recover"
    RETRY = "retry_failed_step"
    ENABLE_SAFE_MODE = "enable_safe_mode"
    DISABLE_SAFE_MODE = "disable_safe_mode"


@dataclass
class ControlRequest:
    request_id: str
    actor_id: str
    mission_id: str
    project_id: str
    trace_id: str
    action: ControlAction
    expected_state: str = ""
    idempotency_key: str = ""
    reason: str = ""
    scope: str = "local"
    created_at: str = field(default_factory=now_iso)


@dataclass
class ControlResult:
    ok: bool
    mission_id: str
    project_id: str
    trace_id: str
    mission_state: str
    approval_state: str = "not_required"
    authorization_state: str = "not_evaluated"
    control_state: str = "autonomous"
    available_actions: list[str] = field(default_factory=list)
    reason_code: str = ""
    reason_message: str = ""
    checkpoint_id: str = ""
    evidence_head: str = ""
    updated_at: str = field(default_factory=now_iso)


class SovereignExecutionCoordinator:
    """Single coordination layer bridging brain modules into product runtime.

    This is the ONLY place that wires Phase A+B governance into the runtime.
    All API endpoints that need approval/authorization MUST route through here.
    """

    def __init__(self, runtime: Any, db_path: str = "runtime/nexara_durable_phase_c.db") -> None:
        self._runtime = runtime
        self._store = runtime.store if hasattr(runtime, 'store') else None
        self._governance = ApprovalOrchestrator()
        self._policy = PolicyRuntime()
        self._policy.bind_orchestrator(self._governance)
        self._authority = AuthorityEngine()
        self._brain_compiler = BrainMissionCompiler()
        self._state_manager = StateManager(db_path=db_path)
        self._recovery = RecoveryEngine(self._state_manager)
        self._safe_mode = False
        # mission_id → ControlState
        self._control_states: dict[str, ControlState] = {}

    # ── Risk → Approval Mapping ──────────────────────────────────────────

    def risk_approval_level(self, risk: RiskLevel | str) -> ApprovalLevel:
        rk = risk.value if isinstance(risk, RiskLevel) else str(risk)
        return RISK_APPROVAL_MAP.get(rk, ApprovalLevel.CONFIRM)

    def requires_approval(self, risk: RiskLevel | str) -> bool:
        rk = risk.value if isinstance(risk, RiskLevel) else str(risk)
        return rk in REQUIRES_APPROVAL

    # ── Mission Lifecycle ─────────────────────────────────────────────────

    def compile_mission(self, objective: str, risk: RiskLevel = RiskLevel.R0,
                        project_id: str = "nexara", constraints: list[str] | None = None,
                        ) -> dict[str, Any]:
        spec, contract = self._brain_compiler.compile(
            objective, risk_level=risk, constraints=constraints or [],
        )
        validation = self._brain_compiler.validate(contract)
        approval_level = self.risk_approval_level(risk)
        return {
            "mission_id": spec.mission_id,
            "title": spec.title,
            "risk_level": risk.value if isinstance(risk, RiskLevel) else str(risk),
            "approval_level": approval_level.value,
            "requires_approval": self.requires_approval(risk),
            "contract_hash": validation.contract_hash,
            "compiled": validation.valid,
            "project_id": project_id,
        }

    def classify_risk(self, mission_id: str, action: str = "execute") -> dict[str, Any]:
        # Delegate to existing runtime risk classification
        try:
            mission = self._runtime.get_mission(mission_id)
            risk = mission.risk_level if hasattr(mission, 'risk_level') else RiskLevel.R0
        except Exception:
            risk = RiskLevel.R0
        auth = self._authority.authorize(
            risk.value if isinstance(risk, RiskLevel) else str(risk),
            "executor", action,
        )
        return {**auth, "mission_id": mission_id}

    # ── Approval (delegates to Phase A+B fail-closed orchestrator) ───────

    def request_approval(self, mission_id: str, project_id: str,
                         risk: str, action: str, resource: str = "*",
                         scope: str = "local") -> dict[str, Any]:
        d = self._governance.request(mission_id, project_id, risk, action,
                                     resource=resource, scope=scope)
        return {
            "decision_id": d.decision_id,
            "mission_id": d.mission_id,
            "project_id": d.project_id,
            "status": d.status.value,
            "approval_level": d.approval_level.value,
            "action": d.action,
            "resource": d.resource,
            "scope": d.scope,
            "issued_at": d.issued_at,
            "nonce": d.nonce,
        }

    def decide_approval(self, decision_id: str, decision: str,
                        approved_by: str = "human") -> dict[str, Any]:
        if decision == "approved":
            d = self._governance.approve(decision_id, approved_by)
        elif decision == "rejected":
            d = self._governance.reject(decision_id, "rejected by human")
        else:
            return {"ok": False, "reason": f"unknown_decision: {decision}"}
        if d is None:
            return {"ok": False, "reason": "decision_not_found"}
        return {
            "ok": True,
            "decision_id": d.decision_id,
            "status": d.status.value,
            "approved_by": d.approved_by,
        }

    def revoke_approval(self, decision_id: str) -> dict[str, Any]:
        d = self._governance.revoke(decision_id)
        if d is None:
            return {"ok": False, "reason": "decision_not_found"}
        return {"ok": True, "decision_id": d.decision_id, "status": d.status.value}

    def verify_approval(self, decision_id: str, mission_id: str,
                        project_id: str, action: str,
                        resource: str = "*") -> dict[str, Any]:
        return self._governance.verify(
            decision_id, mission_id=mission_id, project_id=project_id,
            action=action, resource=resource,
        )

    def pending_approvals(self) -> list[dict[str, Any]]:
        return [
            {
                "decision_id": d.decision_id,
                "mission_id": d.mission_id,
                "project_id": d.project_id,
                "action": d.action,
                "resource": d.resource,
                "risk_level": d.risk_level,
                "approval_level": d.approval_level.value,
                "issued_at": d.issued_at,
            }
            for d in self._governance.pending()
        ]

    # ── Policy / Authorization ────────────────────────────────────────────

    def evaluate_policy(self, risk: str, action: str,
                        allowed_actions: list[str],
                        forbidden_actions: list[str],
                        decision_id: str | None = None,
                        mission_id: str = "",
                        project_id: str = "",
                        resource: str = "*") -> dict[str, Any]:
        return self._policy.enforce(
            risk, action, allowed_actions, forbidden_actions,
            decision_id=decision_id, mission_id=mission_id,
            project_id=project_id, resource=resource,
        )

    # ── Human Control ─────────────────────────────────────────────────────

    def _get_control_state(self, mission_id: str) -> ControlState:
        return self._control_states.get(mission_id, ControlState.AUTONOMOUS)

    def _set_control_state(self, mission_id: str, state: ControlState) -> None:
        self._control_states[mission_id] = state

    def handle_control(self, req: ControlRequest) -> ControlResult:
        cs = self._get_control_state(req.mission_id)
        mission_state = "unknown"
        try:
            m = self._runtime.get_mission(req.mission_id)
            mission_state = m.state.value if hasattr(m.state, 'value') else str(m.state)
        except Exception:
            pass

        action = req.action
        idem_key = req.idempotency_key or f"{action.value}:{req.mission_id}"

        # Check idempotency
        if self._state_manager.is_duplicate(req.project_id, req.mission_id,
                                            action.value, idem_key):
            return ControlResult(
                ok=True, mission_id=req.mission_id, project_id=req.project_id,
                trace_id=req.trace_id, mission_state=mission_state,
                control_state=cs.value, reason_code="duplicate_control_request",
                reason_message="Control action already processed",
            )

        result = self._apply_control(req, cs, mission_state)
        self._state_manager.record_effect(
            req.project_id, req.mission_id, action.value, idem_key,
            hashlib.sha256(f"{action.value}:{result.ok}".encode()).hexdigest()[:16],
        )
        return result

    def _apply_control(self, req: ControlRequest, cs: ControlState,
                       mission_state: str) -> ControlResult:
        action = req.action
        mid = req.mission_id
        pid = req.project_id
        tid = req.trace_id

        # PAUSE
        if action == ControlAction.PAUSE:
            if cs == ControlState.PAUSED:
                return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                    mission_state=mission_state, control_state=cs.value,
                    reason_code="already_paused", reason_message="Mission already paused")
            self._set_control_state(mid, ControlState.PAUSED)
            # Save durable checkpoint
            cp = Checkpoint(new_id("cp"), mid, pid, new_id("run"), tid,
                           "paused", 0, data={"control_action": "pause"})
            self._state_manager.save_checkpoint(cp)
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state="paused",
                reason_code="paused", reason_message="Mission paused by human",
                checkpoint_id=cp.checkpoint_id,
                available_actions=["resume", "cancel", "takeover"])

        # RESUME
        if action == ControlAction.RESUME:
            if cs not in (ControlState.PAUSED, ControlState.HUMAN_CONTROLLED):
                return ControlResult(ok=False, mission_id=mid, project_id=pid, trace_id=tid,
                    mission_state=mission_state, control_state=cs.value,
                    reason_code="cannot_resume", reason_message="Mission not paused or controlled")
            self._set_control_state(mid, ControlState.AUTONOMOUS)
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state="autonomous",
                reason_code="resumed", reason_message="Mission resumed",
                available_actions=["pause", "cancel"])

        # CANCEL
        if action == ControlAction.CANCEL:
            self._set_control_state(mid, ControlState.AUTONOMOUS)
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state="cancelled", control_state="autonomous",
                reason_code="cancelled", reason_message="Mission cancelled by human",
                available_actions=[])

        # TAKEOVER
        if action == ControlAction.TAKEOVER:
            self._set_control_state(mid, ControlState.HUMAN_CONTROLLED)
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state="human_controlled",
                reason_code="takeover", reason_message="Human has taken control",
                available_actions=["release_takeover", "cancel"])

        # RELEASE TAKEOVER
        if action == ControlAction.RELEASE_TAKEOVER:
            if cs != ControlState.HUMAN_CONTROLLED:
                return ControlResult(ok=False, mission_id=mid, project_id=pid, trace_id=tid,
                    mission_state=mission_state, control_state=cs.value,
                    reason_code="not_controlled", reason_message="Mission not under human control")
            self._set_control_state(mid, ControlState.AUTONOMOUS)
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state="autonomous",
                reason_code="released", reason_message="Control released to autonomous",
                available_actions=["pause", "cancel", "takeover"])

        # SAFE MODE
        if action == ControlAction.ENABLE_SAFE_MODE:
            self._safe_mode = True
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state=cs.value,
                reason_code="safe_mode_on", reason_message="Safe mode enabled",
                available_actions=["disable_safe_mode"])
        if action == ControlAction.DISABLE_SAFE_MODE:
            self._safe_mode = False
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state=mission_state, control_state=cs.value,
                reason_code="safe_mode_off", reason_message="Safe mode disabled")

        # RECOVER
        if action == ControlAction.RECOVER:
            cp = self._recovery.recover(mid, pid)
            if cp is None:
                return ControlResult(ok=False, mission_id=mid, project_id=pid, trace_id=tid,
                    mission_state=mission_state, control_state=cs.value,
                    reason_code="no_checkpoint", reason_message="No checkpoint available")
            return ControlResult(ok=True, mission_id=mid, project_id=pid, trace_id=tid,
                mission_state="recovering", control_state=cs.value,
                reason_code="recovered", reason_message="Recovered from checkpoint",
                checkpoint_id=cp.checkpoint_id,
                available_actions=["resume", "cancel"])

        return ControlResult(ok=False, mission_id=mid, project_id=pid, trace_id=tid,
            mission_state=mission_state, control_state=cs.value,
            reason_code="unknown_action", reason_message=f"Unknown control action: {action.value}")

    # ── Mission Status / Available Actions ────────────────────────────────

    def mission_control_status(self, mission_id: str, project_id: str = "nexara"
                               ) -> dict[str, Any]:
        cs = self._get_control_state(mission_id)
        try:
            m = self._runtime.get_mission(mission_id)
            ms = m.state.value if hasattr(m.state, 'value') else str(m.state)
        except Exception:
            ms = "unknown"

        available = []
        if cs == ControlState.AUTONOMOUS:
            available = ["pause", "cancel", "takeover"]
        elif cs == ControlState.PAUSED:
            available = ["resume", "cancel", "takeover"]
        elif cs == ControlState.HUMAN_CONTROLLED:
            available = ["release_takeover", "cancel"]

        return {
            "mission_id": mission_id,
            "project_id": project_id,
            "mission_state": ms,
            "control_state": cs.value,
            "safe_mode": self._safe_mode,
            "available_actions": available,
        }

    def runtime_overview(self) -> dict[str, Any]:
        return {
            "missions_active": len(self._runtime.list_missions()),
            "approvals_pending": len(self._governance.pending()),
            "safe_mode": self._safe_mode,
            "checkpoints": self._state_manager.stats().get("checkpoints", 0),
            "idempotency_records": self._state_manager.stats().get("idempotency_records", 0),
        }
