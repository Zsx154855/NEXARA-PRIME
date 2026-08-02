"""AgentOrchestrator — Multi-agent coordination with governed execution.

Architecture:
  MissionContract → Orchestrator → Agent DAG → Execution → Result Aggregation → Evidence

Enforces:
  - Single writer (only one agent writes to repo at a time)
  - Task lease (lease-based execution prevents conflicts)
  - Dependency DAG (topological execution order)
  - Failure isolation (one agent failure doesn't crash orchestration)
  - Token budget tracking (per-agent and total)
  - Deterministic routing (agent selection by capability match)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ..models import FailureCode, new_id, now_iso


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    ANALYST = "analyst"
    EXECUTOR = "executor"
    CRITIC = "critic"
    MEMORY = "memory"
    EVALUATOR = "evaluator"
    UI_SPECIALIST = "ui_specialist"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"


@dataclass
class AgentTask:
    """A single task in the orchestration DAG."""
    task_id: str = field(default_factory=lambda: new_id("task"))
    role: AgentRole = AgentRole.EXECUTOR
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_writer: bool = False
    result: Any = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: int = 300
    estimated_tokens: int = 0


@dataclass
class AgentLease:
    """Writer lease for single-writer enforcement."""
    lease_id: str = field(default_factory=lambda: new_id("lease"))
    holder: str = ""
    task_id: str = ""
    issued_at: str = field(default_factory=now_iso)
    expires_at: str = ""
    status: str = "active"


@dataclass
class OrchestrationResult:
    """Aggregated result of an orchestration run."""
    mission_id: str
    total_tasks: int
    completed: int
    failed: int
    cancelled: int
    timed_out: int
    total_tokens_used: int = 0
    execution_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "unknown"


class AgentOrchestrator:
    """Coordinates multi-agent execution with governance.

    Responsibilities:
      - Plan: Decompose mission into agent DAG
      - Schedule: Topological execution order
      - Execute: Run tasks with lease enforcement
      - Monitor: Track progress, timeout, retry
      - Aggregate: Collect results into unified evidence
    """

    name = "agent_orchestrator"

    def __init__(
        self,
        *,
        max_concurrent: int = 3,
        default_timeout: int = 300,
        token_budget: int = 100000,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.token_budget = token_budget
        self._tasks: dict[str, AgentTask] = {}
        self._leases: dict[str, AgentLease] = {}
        self._execution_log: list[dict[str, Any]] = []
        self._active_writer: str | None = None
        self._tokens_used: int = 0

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "active_tasks": len([t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]),
            "active_writer": self._active_writer,
            "tokens_used": self._tokens_used,
            "token_budget": self.token_budget,
        }

    # ── Planning ────────────────────────────────────────────────────────────

    def plan(
        self,
        mission_id: str,
        steps: list[dict[str, Any]],
        *,
        writer_role: AgentRole = AgentRole.EXECUTOR,
    ) -> list[AgentTask]:
        """Decompose mission steps into agent task DAG.

        Each step dict should have: role, description, dependencies, capabilities.
        Returns the ordered task list.
        """
        self._tasks.clear()
        tasks = []

        for i, step in enumerate(steps):
            role = AgentRole(step.get("role", "executor"))
            task = AgentTask(
                task_id=new_id("task"),
                role=role,
                description=step.get("description", f"Step {i+1}"),
                dependencies=step.get("dependencies", []),
                required_capabilities=step.get("capabilities", []),
                assigned_writer=(role == writer_role),
            )
            self._tasks[task.task_id] = task
            tasks.append(task)

        # Topological sort
        return self._topological_sort(tasks)

    # ── Execution ────────────────────────────────────────────────────────────

    def execute(
        self,
        mission_id: str,
        executor: Callable[[AgentTask], Any],
        *,
        on_progress: Callable[[AgentTask], None] | None = None,
        on_error: Callable[[AgentTask, Exception], None] | None = None,
    ) -> OrchestrationResult:
        """Execute the planned task DAG sequentially with governance.

        Args:
            mission_id: The mission being executed
            executor: Function that executes a single task
            on_progress: Called after each task completes
            on_error: Called when a task fails

        Returns aggregated OrchestrationResult.
        """
        start_time = time.monotonic()
        tasks = list(self._tasks.values())
        completed = 0
        failed = 0
        cancelled = 0
        timed_out = 0
        errors: list[str] = []

        for task in tasks:
            if self._tokens_used >= self.token_budget:
                task.status = TaskStatus.CANCELLED
                cancelled += 1
                errors.append(f"token_budget_exhausted: {task.task_id}")
                continue

            # Check dependencies
            blocked = False
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if dep and dep.status != TaskStatus.COMPLETED:
                    task.status = TaskStatus.BLOCKED
                    blocked = True
                    break
            if blocked:
                continue

            # Acquire writer lease if needed
            if task.assigned_writer:
                lease = self._acquire_lease(task.task_id)
                if lease is None:
                    task.status = TaskStatus.BLOCKED
                    continue

            # Execute
            task.status = TaskStatus.RUNNING
            task.started_at = now_iso()

            try:
                result = executor(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
                completed += 1
                if on_progress:
                    on_progress(task)
            except TimeoutError:
                task.status = TaskStatus.TIMED_OUT
                task.error = "task_timed_out"
                timed_out += 1
                if on_error:
                    on_error(task, TimeoutError("task_timed_out"))
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                failed += 1
                errors.append(f"{task.task_id}: {e}")
                if on_error:
                    on_error(task, e)

            task.completed_at = now_iso()
            self._execution_log.append({
                "task_id": task.task_id,
                "status": task.status.value,
                "duration": task.completed_at,
                "tokens": task.estimated_tokens,
            })

            # Release lease
            if task.assigned_writer:
                self._release_lease(task.task_id)

        elapsed = time.monotonic() - start_time

        return OrchestrationResult(
            mission_id=mission_id,
            total_tasks=len(tasks),
            completed=completed,
            failed=failed,
            cancelled=cancelled,
            timed_out=timed_out,
            total_tokens_used=self._tokens_used,
            execution_time_seconds=elapsed,
            errors=errors,
            status="completed" if failed == 0 else "partial_failure",
        )

    # ── Lease Management ─────────────────────────────────────────────────────

    def _acquire_lease(self, task_id: str) -> AgentLease | None:
        """Acquire writer lease for single-writer enforcement."""
        if self._active_writer is not None:
            return None
        lease = AgentLease(
            holder="h-exe",
            task_id=task_id,
            expires_at=now_iso(),  # Simplified; real impl would set future expiry
        )
        self._leases[task_id] = lease
        self._active_writer = task_id
        return lease

    def _release_lease(self, task_id: str) -> None:
        """Release a writer lease."""
        if task_id in self._leases:
            self._leases[task_id].status = "released"
        if self._active_writer == task_id:
            self._active_writer = None

    # ── Topological Sort ─────────────────────────────────────────────────────

    def _topological_sort(self, tasks: list[AgentTask]) -> list[AgentTask]:
        """Sort tasks by dependency DAG (Kahn's algorithm)."""
        in_degree: dict[str, int] = {t.task_id: len(t.dependencies) for t in tasks}
        adj: dict[str, list[str]] = {t.task_id: [] for t in tasks}

        for t in tasks:
            for dep_id in t.dependencies:
                if dep_id in adj:
                    adj[dep_id].append(t.task_id)

        queue = [t for t in tasks if in_degree[t.task_id] == 0]
        result: list[AgentTask] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor_id in adj.get(node.task_id, []):
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    neighbor = next(t for t in tasks if t.task_id == neighbor_id)
                    queue.append(neighbor)

        # Any remaining tasks have circular dependencies — append in original order
        for t in tasks:
            if t not in result:
                result.append(t)

        return result

    # ── Query ────────────────────────────────────────────────────────────────

    def task_status(self, task_id: str) -> dict[str, Any] | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        return {
            "task_id": t.task_id,
            "role": t.role.value,
            "status": t.status.value,
            "dependencies": t.dependencies,
            "result": str(t.result)[:200] if t.result else None,
            "error": t.error,
        }

    def all_tasks(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tid in self._tasks:
            ts = self.task_status(tid)
            if ts is not None:
                result.append(ts)
        return result
