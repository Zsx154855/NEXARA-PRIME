"""MissionCompiler — Compiles human intent into formal NEXARA Mission Contracts.

Architecture:
  User Intent → analyze → MissionSpec → compile → WorkContract → validate → Evidence

The compiler enforces:
  - Schema validation (contract version, required fields)
  - Deterministic compilation (same input → same output)
  - Canonical hashing (contract content hash for evidence binding)
  - Idempotency (duplicate mission prevention)
  - Risk classification (R0-R4 mapping from intent analysis)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..models import (
    FailureCode,
    Mission,
    MissionSpec,
    MissionState,
    RiskLevel,
    WorkContract,
    new_id,
    now_iso,
)


class MissionCompileError(ValueError):
    """Raised when mission compilation fails."""
    def __init__(self, reason: str, failure_code: FailureCode = FailureCode.TOOL_ARGUMENT_INVALID):
        self.failure_code = failure_code
        super().__init__(reason)


class MissionValidationResult:
    """Result of mission contract validation."""
    def __init__(
        self,
        valid: bool,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        contract_hash: str | None = None,
    ):
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.contract_hash = contract_hash


class MissionCompiler:
    """Compiles human intent into formal, validated mission contracts.

    Provides:
      - analyze(): Intent → structured analysis
      - compile(): Intent → MissionSpec + WorkContract
      - validate(): Contract integrity check
      - hash_contract(): Canonical content hash
    """

    name = "mission_compiler"

    def __init__(self) -> None:
        self._compiled_hashes: set[str] = set()
        self._compiled_count: int = 0

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "compiled_count": self._compiled_count,
            "duplicate_prevention": len(self._compiled_hashes),
        }

    # ── Intent Analysis ─────────────────────────────────────────────────────

    def analyze(self, objective: str, constraints: list[str] | None = None) -> dict[str, Any]:
        """Analyze raw intent and produce structured analysis.

        Returns dict with:
          - objective, inferred_risk, suggested_boundaries,
          - required_capabilities, estimated_complexity, acceptance_criteria
        """
        risk = self._infer_risk(objective, constraints or [])
        complexity = self._estimate_complexity(objective)

        return {
            "objective": objective,
            "inferred_risk": risk.value,
            "estimated_complexity": complexity,
            "suggested_boundaries": self._suggest_boundaries(objective),
            "required_capabilities": self._required_capabilities(objective, risk),
            "acceptance_criteria": self._derive_acceptance(objective),
            "timestamp": now_iso(),
        }

    # ── Compilation ──────────────────────────────────────────────────────────

    def compile(
        self,
        objective: str,
        *,
        title: str | None = None,
        constraints: list[str] | None = None,
        risk_level: RiskLevel | None = None,
        boundaries: list[str] | None = None,
        deliverables: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        source_dir: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[MissionSpec, WorkContract]:
        """Compile human intent into formal MissionSpec + WorkContract.

        The compilation is deterministic: same inputs produce same outputs.
        Idempotency is enforced via content hash deduplication.
        """
        analysis = self.analyze(objective, constraints)

        spec = MissionSpec(
            title=title or self._derive_title(objective),
            objective=objective,
            boundaries=boundaries or analysis["suggested_boundaries"],
            constraints=constraints or [],
            deliverables=deliverables or self._default_deliverables(objective),
            risks=[],
            acceptance_criteria=acceptance_criteria or analysis["acceptance_criteria"],
            risk_level=risk_level or RiskLevel(analysis["inferred_risk"]),
            source_dir=source_dir,
            correlation_id=correlation_id,
        )

        contract = WorkContract(
            mission_id=spec.mission_id,
            objective=objective,
            boundaries=spec.boundaries,
            constraints=spec.constraints,
            deliverables=spec.deliverables,
            acceptance_criteria=spec.acceptance_criteria,
            risk_level=spec.risk_level,
            correlation_id=correlation_id,
            provenance="mission_compiler_v1",
        )

        # Idempotency: prevent duplicate compilation
        ch = self._hash_contract(contract)
        if ch in self._compiled_hashes:
            raise MissionCompileError(
                f"Duplicate mission detected (hash={ch[:12]}). Same objective+constraints already compiled.",
                FailureCode.INTEGRITY_IDEMPOTENCY_CONFLICT,
            )
        self._compiled_hashes.add(ch)
        self._compiled_count += 1

        return spec, contract

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self, contract: WorkContract) -> MissionValidationResult:
        """Validate a compiled contract for integrity and completeness."""
        errors: list[str] = []
        warnings: list[str] = []

        if not contract.objective or len(contract.objective.strip()) < 3:
            errors.append("objective_too_short: must be at least 3 characters")

        if len(contract.objective) > 2000:
            warnings.append("objective_very_long: consider shortening")

        if not contract.acceptance_criteria:
            errors.append("missing_acceptance_criteria: at least one required")

        if contract.risk_level not in RiskLevel:
            errors.append(f"invalid_risk_level: {contract.risk_level}")

        if contract.schema_version < 1:
            errors.append("invalid_schema_version")

        contract_hash = self._hash_contract(contract)

        return MissionValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            contract_hash=contract_hash,
        )

    # ── Hashing ──────────────────────────────────────────────────────────────

    def _hash_contract(self, contract: WorkContract) -> str:
        """Compute canonical SHA-256 of contract content for evidence binding."""
        payload = {
            "objective": contract.objective,
            "boundaries": sorted(contract.boundaries),
            "constraints": sorted(contract.constraints),
            "deliverables": sorted(contract.deliverables),
            "acceptance_criteria": sorted(contract.acceptance_criteria),
            "risk_level": contract.risk_level.value,
            "schema_version": contract.schema_version,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    # ── Private Helpers ──────────────────────────────────────────────────────

    def _infer_risk(self, objective: str, constraints: list[str]) -> RiskLevel:
        """Infer risk level from objective keywords and constraints."""
        olower = objective.lower()
        if any(w in olower for w in ["deploy", "push", "merge", "delete", "destroy", "sudo", "force"]):
            return RiskLevel.R4
        if any(w in olower for w in ["modify", "write", "create", "update", "install", "commit"]):
            return RiskLevel.R2
        if any(w in olower for w in ["read", "list", "view", "check", "status", "audit", "inspect"]):
            return RiskLevel.R0
        if constraints and any("approval" in c.lower() or "human" in c.lower() for c in constraints):
            return RiskLevel.R3
        return RiskLevel.R2

    def _estimate_complexity(self, objective: str) -> float:
        """Estimate complexity 0.0-1.0 from objective length and keyword density."""
        words = len(objective.split())
        action_words = sum(1 for w in objective.lower().split()
                          if w in ["deploy", "compile", "build", "test", "analyze", "migrate", "refactor"])
        return min(1.0, 0.3 + (words / 100.0) + (action_words * 0.1))

    def _suggest_boundaries(self, objective: str) -> list[str]:
        """Suggest safe boundaries for the mission."""
        return [
            "read_only_filesystem",
            "no_network_outbound",
            "no_git_push",
            "no_system_modification",
        ]

    def _required_capabilities(self, objective: str, risk: RiskLevel) -> list[str]:
        """Determine required capabilities from objective and risk."""
        caps = ["file_read", "terminal_read"]
        olower = objective.lower()
        if any(w in olower for w in ["write", "create", "modify", "generate"]):
            caps.append("file_write")
        if any(w in olower for w in ["test", "pytest", "verify"]):
            caps.append("test_execution")
        if any(w in olower for w in ["build", "compile"]):
            caps.append("build_execution")
        if risk in (RiskLevel.R3, RiskLevel.R4):
            caps.append("human_approval")
        return caps

    def _derive_acceptance(self, objective: str) -> list[str]:
        """Derive acceptance criteria from objective."""
        return [
            "mission_completes_without_error",
            "evidence_package_is_complete",
            "receipt_is_valid_and_signed",
            "output_matches_expected_format",
        ]

    def _derive_title(self, objective: str) -> str:
        """Derive a short title from the objective."""
        words = objective.strip().split()
        if len(words) <= 8:
            return objective.strip()
        return " ".join(words[:8]) + "..."

    def _default_deliverables(self, objective: str) -> list[str]:
        """Default deliverables for any mission."""
        return ["mission_evidence", "mission_receipt", "final_output"]


def compile_mission(
    objective: str,
    *,
    title: str | None = None,
    constraints: list[str] | None = None,
    risk_level: RiskLevel | None = None,
) -> tuple[MissionSpec, WorkContract]:
    """Convenience function: one-shot compile."""
    compiler = MissionCompiler()
    return compiler.compile(
        objective,
        title=title,
        constraints=constraints,
        risk_level=risk_level,
    )
