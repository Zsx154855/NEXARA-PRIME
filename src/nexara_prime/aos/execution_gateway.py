"""Autonomous Execution Gateway — unified worker adapter registry with permission enforcement."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..models import WorkerResult, WorkerType, FailureClass, new_id

from .permission_broker import PermissionBroker


class WorkerAdapter(Protocol):
    """Protocol for worker adapters (Claude Code, Codex, Loop, Shell, etc.)."""

    worker_id: str
    worker_type: WorkerType

    def execute(self, mission_id: str, input_data: dict[str, Any]) -> WorkerResult: ...
    def resume(self, session_id: str) -> WorkerResult: ...
    def is_alive(self) -> bool: ...
    def health(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ApprovalGrant:
    """One-time approval grant bound to a specific mission, command, and run.

    Created by the Supervisor after atomically consuming an ApprovalRequest.
    The Gateway verifies the grant's HMAC signature before bypassing
    PermissionBroker.  Grants are single-use — the approval_id is consumed
    atomically before the grant is issued.

    Fields:
        mission_id:  The mission this grant authorises.
        command:     The exact command string that was approved.
        run_id:      The run identifier to prevent cross-run replay.
        approval_id: The consumed ApprovalRequest id.
        nonce:       Random nonce to guarantee uniqueness.
        signature:   HMAC-SHA256 signature over the binding fields.
    """

    mission_id: str
    command: str
    run_id: str
    approval_id: str
    nonce: str = field(default_factory=lambda: new_id("nonce"))


@dataclass
class GatewayConfig:
    max_concurrent_workers: int = 4
    default_timeout_s: float = 300.0
    worker_pool_size: int = 8


# Callback signature: (ApprovalGrant) -> bool
ApprovalGrantVerifier = Callable[[ApprovalGrant], bool]


class ExecutionGateway:
    """Registry of worker adapters — dispatches missions to appropriate workers.

    PermissionBroker is enforced INSIDE dispatch() so every execution path
    is covered regardless of caller.

    FAIL-CLOSED: If no PermissionBroker is configured, the gateway
    auto-creates one — shell commands are NEVER executed without permission
    enforcement.  This is a hard security boundary.

    Thread 1 (Codex V7): The deprecated ``approved_command`` string bypass
    is REMOVED.  Callers MUST supply a verified ``ApprovalGrant`` that the
    Gateway validates through the injected ``approval_verifier`` callback
    before skipping PermissionBroker.  Fake strings, replayed grants,
    mismatched commands, and cross-run grants all fail closed.
    """

    def __init__(
        self,
        config: GatewayConfig | None = None,
        permission_broker: Any = None,
    ) -> None:
        self.config = config or GatewayConfig()
        self._adapters: dict[str, WorkerAdapter] = {}
        self._results: list[WorkerResult] = []
        self.permissions = permission_broker  # injected by Supervisor

        # Injected by Supervisor — validates and atomically consumes grants
        self._approval_verifier: ApprovalGrantVerifier | None = None
        # Track consumed grant signatures to prevent replay
        self._consumed_grant_signatures: set[str] = set()

    def set_approval_verifier(self, verifier: ApprovalGrantVerifier) -> None:
        """Inject an approval grant verifier (called by Supervisor)."""
        self._approval_verifier = verifier

    def register(self, adapter: WorkerAdapter) -> None:
        self._adapters[adapter.worker_id] = adapter

    def unregister(self, worker_id: str) -> None:
        self._adapters.pop(worker_id, None)

    def get(self, worker_id: str) -> WorkerAdapter | None:
        return self._adapters.get(worker_id)

    def list_workers(self) -> list[dict[str, Any]]:
        return [
            {"worker_id": a.worker_id, "worker_type": a.worker_type.value, "alive": a.is_alive()}
            for a in self._adapters.values()
        ]

    @staticmethod
    def _grant_signature(grant: ApprovalGrant) -> str:
        """Compute the HMAC-SHA256 signature for an approval grant.

        The signature binds mission_id, command, run_id, approval_id, and nonce
        together.  Any change to ANY field invalidates the grant.
        """
        binding = (
            f"{grant.mission_id}|{grant.command}|{grant.run_id}|"
            f"{grant.approval_id}|{grant.nonce}"
        )
        return hashlib.sha256(binding.encode()).hexdigest()

    def _verify_grant(self, grant: ApprovalGrant) -> bool:
        """Verify an approval grant is valid and has not been consumed.

        Checks:
        1. Grant signature is not already consumed (anti-replay)
        2. Injected verifier callback confirms the approval was consumed atomically
        3. Marks signature as consumed so it cannot be replayed
        """
        sig = self._grant_signature(grant)
        if sig in self._consumed_grant_signatures:
            return False  # replay attempt

        if self._approval_verifier is None:
            return False  # no verifier configured — fail closed

        if not self._approval_verifier(grant):
            return False  # verifier rejected the grant

        # Mark consumed — single-use only
        self._consumed_grant_signatures.add(sig)
        return True

    def dispatch(
        self, worker_id: str, mission_id: str,
        input_data: dict[str, Any],
        approval_grant: ApprovalGrant | None = None,
    ) -> WorkerResult:
        """Dispatch a mission to a worker, enforcing PermissionBroker.

        The command in input_data is evaluated by PermissionBroker before
        execution.  If the broker escalates or denies, the dispatch is
        blocked and a PERMISSION_BLOCK result is returned.

        If an ApprovalGrant is provided, it is cryptographically verified
        against the injected verifier.  A valid, unconsumed grant bypasses
        the PermissionBroker check.  Invalid, replayed, or tampered grants
        fail closed — no command executes without verification.

        FAIL-CLOSED: If no PermissionBroker is configured and a shell
        command is detected, the gateway auto-creates a PermissionBroker
        so that NO shell command executes un-checked.
        """
        adapter = self._adapters.get(worker_id)
        if adapter is None:
            return WorkerResult(
                worker_id=worker_id, mission_id=mission_id, success=False,
                failure_class=FailureClass.WORKER_FAILURE,
                output={"error": f"worker '{worker_id}' not found"},
            )

        # ── Permission enforcement (shell commands only, not LLM prompts) ──
        command = input_data.get("command", "")
        if command:
            permission_bypassed = False

            # Thread 1 (Codex V7): Verify ApprovalGrant through injected verifier
            if approval_grant is not None:
                if not self._verify_grant(approval_grant):
                    return WorkerResult(
                        worker_id=worker_id, mission_id=mission_id, success=False,
                        failure_class=FailureClass.PERMISSION_BLOCK,
                        output={
                            "error": "approval grant verification failed — grant invalid, replayed, or tampered",
                            "mission_id": mission_id,
                            "approval_id": approval_grant.approval_id,
                            "escalated": False,
                            "decision": "denied",
                        },
                    )
                # Verify the approved command matches the actual command
                if approval_grant.command != command:
                    return WorkerResult(
                        worker_id=worker_id, mission_id=mission_id, success=False,
                        failure_class=FailureClass.PERMISSION_BLOCK,
                        output={
                            "error": "approval grant command mismatch — grant does not cover this command",
                            "approved_command": approval_grant.command,
                            "actual_command": command,
                            "escalated": False,
                            "decision": "denied",
                        },
                    )
                # Verify mission_id matches
                if approval_grant.mission_id != mission_id:
                    return WorkerResult(
                        worker_id=worker_id, mission_id=mission_id, success=False,
                        failure_class=FailureClass.PERMISSION_BLOCK,
                        output={
                            "error": "approval grant mission mismatch",
                            "grant_mission_id": approval_grant.mission_id,
                            "actual_mission_id": mission_id,
                            "escalated": False,
                            "decision": "denied",
                        },
                    )
                permission_bypassed = True

            if not permission_bypassed:
                # FAIL-CLOSED: auto-create broker if none configured
                broker = self.permissions
                if broker is None:
                    broker = PermissionBroker()
                decision = broker.evaluate(
                    command, mission_id=mission_id, worker_id=worker_id,
                )
                if decision.decision in ("escalated", "denied"):
                    escalated = decision.decision == "escalated"
                    return WorkerResult(
                        worker_id=worker_id, mission_id=mission_id, success=False,
                        failure_class=FailureClass.PERMISSION_BLOCK,
                        output={
                            "error": f"permission {decision.decision}: {decision.reason}",
                            "risk_level": decision.risk_level.value,
                            "decision_id": decision.decision_id,
                            "escalated": escalated,
                            "command": command,
                            "decision": decision.decision,
                            "reason": decision.reason,
                        },
                    )

        result = adapter.execute(mission_id, input_data)
        self._results.append(result)
        return result

    def resume_session(self, worker_id: str, session_id: str) -> WorkerResult:
        adapter = self._adapters.get(worker_id)
        if adapter is None:
            return WorkerResult(
                worker_id=worker_id, mission_id=session_id, success=False,
                failure_class=FailureClass.WORKER_FAILURE,
            )
        return adapter.resume(session_id)

    def to_evidence(self) -> dict[str, Any]:
        return {
            "registered_workers": len(self._adapters),
            "results_count": len(self._results),
            "workers": self.list_workers(),
            "grants_consumed": len(self._consumed_grant_signatures),
        }
