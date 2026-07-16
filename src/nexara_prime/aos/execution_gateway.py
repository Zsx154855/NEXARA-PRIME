"""Autonomous Execution Gateway — unified worker adapter registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..models import WorkerResult, WorkerType, FailureClass


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
    """Registry of worker adapters — dispatches missions to appropriate workers."""

    def __init__(self, config: GatewayConfig | None = None) -> None:
        self.config = config or GatewayConfig()
        self._adapters: dict[str, WorkerAdapter] = {}
        self._results: list[WorkerResult] = []

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

    def dispatch(self, worker_id: str, mission_id: str,
                 input_data: dict[str, Any]) -> WorkerResult:
        adapter = self._adapters.get(worker_id)
        if adapter is None:
            return WorkerResult(
                worker_id=worker_id, mission_id=mission_id, success=False,
                failure_class=FailureClass.WORKER_FAILURE,
                output={"error": f"worker '{worker_id}' not found"},
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
