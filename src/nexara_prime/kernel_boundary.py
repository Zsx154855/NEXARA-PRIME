"""Kernel Boundary — enforcement primitives for ChiefBrainKernel admission.

These types define the enforcement contract. ChiefBrainKernel owns admission.
NexaraRuntime owns execution. Neither can operate without the other.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class KernelBoundaryViolation(RuntimeError):
    """Raised when kernel admission is bypassed or a required gate is missing."""


class GovernanceViolation(KernelBoundaryViolation):
    """Raised when governance approval is missing or bypassed."""


class ExecutionBoundaryViolation(KernelBoundaryViolation):
    """Raised when runtime execution is attempted without kernel admission."""


@dataclass(frozen=True)
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
        missing = [k for k, v in gates.items() if v is not True]
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
    _live_admission_validator: Callable[[KernelAdmissionContext], bool] | None = None

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
        # Always recheck at execution, including unusual Python-level mutation.
        # This does not authenticate the original issuer or revocation status.
        try:
            self._active_context.assert_complete()
        except KernelBoundaryViolation:
            self.clear()
            raise
        if self._live_admission_validator is not None:
            try:
                currently_valid = self._live_admission_validator(self._active_context)
            except Exception as exc:
                self.clear()
                raise ExecutionBoundaryViolation("Admission freshness check failed") from exc
            if currently_valid is not True:
                self.clear()
                raise ExecutionBoundaryViolation("Admission no longer valid")
        return self._active_context

    def clear(self) -> None:
        self._active_context = None
