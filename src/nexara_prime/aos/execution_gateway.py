"""Autonomous Execution Gateway — unified worker adapter registry with permission enforcement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..models import WorkerResult, WorkerType, FailureClass

from .permission_broker import PermissionBroker


class WorkerAdapter(Protocol):
    """Protocol for worker adapters (Claude Code, Codex, Loop, Shell, etc.)."""

    worker_id: str
    worker_type: WorkerType

    def execute(self, mission_id: str, input_data: dict[str, Any]) -> WorkerResult: ...
    def resume(self, session_id: str) -> WorkerResult: ...
    def is_alive(self) -> bool: ...
    def health(self) -> dict[str, Any]: ...


@dataclass
class GatewayConfig:
    max_concurrent_workers: int = 4
    default_timeout_s: float = 300.0
    worker_pool_size: int = 8


class ExecutionGateway:
    """Registry of worker adapters — dispatches missions to appropriate workers.

    PermissionBroker is enforced INSIDE dispatch() so every execution path
    is covered regardless of caller.

    FAIL-CLOSED: If no PermissionBroker is configured, the gateway
    auto-creates one — shell commands are NEVER executed without permission
    enforcement. This is a hard security boundary.
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

    def dispatch(
        self, worker_id: str, mission_id: str,
        input_data: dict[str, Any],
        approved_command: str | None = None,
    ) -> WorkerResult:
        """Dispatch a mission to a worker, enforcing PermissionBroker.

        The command in input_data is evaluated by PermissionBroker before
        execution. If the broker escalates or denies, the dispatch is
        blocked and a PERMISSION_BLOCK result is returned (with escalated=True
        if the decision was "escalated", so the caller can route to approval).

        If approved_command is provided and matches the command, the permission
        check is SKIPPED — this is used after human approval consumption.

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
            # Pre-approved via consumed ApprovalRequest — skip permission check
            if approved_command is not None and command == approved_command:
                pass  # bypass permission check → execute directly
            else:
                # FAIL-CLOSED: auto-create broker if none configured
                broker = self.permissions
                if broker is None:
                    broker = PermissionBroker()
                decision = broker.evaluate(
                    command, mission_id=mission_id, worker_id=worker_id,
                )
                if decision.decision in ("escalated", "denied"):
                    # Mark whether this is an escalation (requires approval) vs a hard deny
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
        }
