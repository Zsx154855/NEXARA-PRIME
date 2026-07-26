"""Kernel Boundary — enforcement primitives for ChiefBrainKernel admission.

These types define the enforcement contract. ChiefBrainKernel owns admission.
NexaraRuntime owns execution. Neither can operate without the other.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class KernelBoundaryViolation(RuntimeError):
    """Raised when kernel admission is bypassed or a required gate is missing."""


class GovernanceViolation(KernelBoundaryViolation):
    """Raised when governance approval is missing or bypassed."""


class ExecutionBoundaryViolation(KernelBoundaryViolation):
    """Raised when runtime execution is attempted without kernel admission."""


@dataclass
class KernelAdmissionContext:
    """Proof that a mission has passed all kernel admission gates.

    Created by ChiefBrainKernel.submit(). Required by Runtime for execution.
    """
    mission_id: str
    caller: str
    contract_verified: bool = False
    authority_verified: bool = False
    state_valid: bool = False
    governance_approved: bool = False
    evidence_chain_initialized: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def assert_complete(self) -> None:
        """All gates must pass before execution. Raises KernelBoundaryViolation."""
        gates = {
            "contract_verified": self.contract_verified,
            "authority_verified": self.authority_verified,
            "state_valid": self.state_valid,
            "governance_approved": self.governance_approved,
            "evidence_chain_initialized": self.evidence_chain_initialized,
        }
        missing = [k for k, v in gates.items() if not v]
        if missing:
            raise KernelBoundaryViolation(
                "Kernel admission incomplete for mission {}: missing {}".format(
                    self.mission_id, missing))


@dataclass
class KernelExecutionGuard:
    """Protects Runtime internal execution paths.

    Runtime execution requires a valid KernelAdmissionContext.
    Without it, execution is blocked.
    """
    _active_context: KernelAdmissionContext | None = None

    def admit(self, ctx: KernelAdmissionContext) -> None:
        ctx.assert_complete()
        self._active_context = ctx

    def assert_admitted(self, mission_id: str) -> KernelAdmissionContext:
        if self._active_context is None:
            raise ExecutionBoundaryViolation(
                "No kernel admission context. Call kernel.submit() first.")
        if self._active_context.mission_id != mission_id:
            raise ExecutionBoundaryViolation(
                "Admission context for {} does not match requested {}".format(
                    self._active_context.mission_id, mission_id))
        return self._active_context

    def clear(self) -> None:
        self._active_context = None
