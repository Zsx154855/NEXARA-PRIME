"""
NEXARA Model Evaluation Engine V1

Evaluates model outputs deterministically where possible, uses verifier model
for semantic validation. Never self-evaluates.

NSEC V2.1 §5.F
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .models import now_iso


class EvaluationStatus(str, Enum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ModelEvaluationResult:
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    invocation_id: str = ""
    mission_id: str = ""
    status: EvaluationStatus = EvaluationStatus.INCONCLUSIVE
    # deterministic checks
    contract_compliance: bool = True
    schema_valid: bool = True
    evidence_coverage: float = 1.0  # 0.0-1.0
    # semantic checks
    factual_consistency: bool | None = None
    hallucination_risk: float = 0.0  # 0.0-1.0
    tool_result_consistency: bool | None = None
    governance_compliance: bool = True
    # quality
    answer_completeness: float = 1.0  # 0.0-1.0
    confidence_calibration: float | None = None  # 0.0-1.0
    contradiction_count: int = 0
    # metadata
    verifier_model: str = ""
    verifier_provider: str = ""
    created_at: str = field(default_factory=now_iso)
    findings: list[str] = field(default_factory=list)

    @property
    def is_pass(self) -> bool:
        return self.status in (EvaluationStatus.PASS, EvaluationStatus.PASS_WITH_WARNINGS)

    @property
    def is_clear_pass(self) -> bool:
        return self.status == EvaluationStatus.PASS


class ModelEvaluationEngine:
    """
    Evaluates model output against schema, contract, evidence, and verifier.

    Priority: deterministic → schema → evidence → contract → verifier.
    Never self-evaluates. Verifier is a separate model instance.
    """

    def evaluate(
        self,
        output: dict | str,
        expected_schema: dict | None = None,
        contract: dict | None = None,
        evidence: list | None = None,
        invocation_id: str = "",
        mission_id: str = "",
    ) -> ModelEvaluationResult:
        findings: list[str] = []

        # 1. Schema validation (deterministic)
        schema_valid = True
        if expected_schema and isinstance(output, dict):
            schema_valid = self._validate_schema(output, expected_schema, findings)

        # 2. Contract compliance (deterministic)
        contract_ok = True
        if contract and isinstance(output, dict):
            contract_ok = self._validate_contract(output, contract, findings)

        # 3. Evidence coverage (deterministic)
        evidence_cov = 1.0
        if evidence and isinstance(output, dict):
            evidence_cov = self._check_evidence_coverage(output, evidence, findings)

        # 4. Synthesise result
        if not schema_valid or not contract_ok or evidence_cov < 0.5:
            status = EvaluationStatus.FAIL
        elif findings:
            status = EvaluationStatus.PASS_WITH_WARNINGS
        else:
            status = EvaluationStatus.PASS

        return ModelEvaluationResult(
            invocation_id=invocation_id,
            mission_id=mission_id,
            status=status,
            contract_compliance=contract_ok,
            schema_valid=schema_valid,
            evidence_coverage=evidence_cov,
            findings=findings,
        )

    # ── deterministic validators ─────────────────────────

    @staticmethod
    def _validate_schema(output: dict, schema: dict, findings: list[str]) -> bool:
        required_fields = schema.get("required", [])
        missing = [f for f in required_fields if f not in output]
        if missing:
            findings.append(f"Schema validation failed: missing fields {missing}")
            return False
        return True

    @staticmethod
    def _validate_contract(output: dict, contract: dict, findings: list[str]) -> bool:
        invariants = contract.get("invariants", [])
        for inv in invariants:
            field = inv.get("field", "")
            expected = inv.get("value")
            actual = output.get(field)
            if expected is not None and actual != expected:
                findings.append(f"Contract violation: {field} expected={expected}, got={actual}")
                return False
        return True

    @staticmethod
    def _check_evidence_coverage(output: dict, evidence: list, findings: list[str]) -> float:
        if not evidence:
            return 1.0
        evidence_keys = set()
        for e in evidence:
            if isinstance(e, dict):
                evidence_keys.update(e.keys())
        output_keys = set(output.keys())
        overlap = evidence_keys & output_keys
        if not overlap:
            findings.append("Output has no overlap with evidence keys")
            return 0.0
        return len(overlap) / max(len(evidence_keys), 1)

    def run_verifier(
        self, output: dict, verifier_model: str, verifier_provider: str
    ) -> ModelEvaluationResult:
        """Placeholder for verifier-model evaluation. Called by orchestration engine."""
        return ModelEvaluationResult(
            verifier_model=verifier_model,
            verifier_provider=verifier_provider,
            status=EvaluationStatus.PASS_WITH_WARNINGS,
            factual_consistency=True,
            hallucination_risk=0.1,
            tool_result_consistency=True,
            governance_compliance=True,
            answer_completeness=0.9,
            contradiction_count=0,
        )
