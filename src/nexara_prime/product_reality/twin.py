from __future__ import annotations

import hashlib
import json
from typing import Any

from nexara_prime.db import SQLiteStore
from nexara_prime.models import RiskLevel

from .models import (
    DriftFinding,
    DriftType,
    DriftValue,
    ProductTwinCheckpoint,
    TwinSnapshot,
)


class ProductTwinEngine:
    """Capture expected/observed product state and detect deterministic drift."""

    def __init__(self, store: SQLiteStore | None = None):
        self.store = store

    def capture(
        self,
        *,
        mission_id: str,
        expected_state: dict[str, Any],
        observed_state: dict[str, Any],
        evidence_refs: list[str] | None = None,
        reversible: bool = True,
        rollback_ref: str | None = None,
    ) -> ProductTwinCheckpoint:
        refs = evidence_refs or []
        expected = self._snapshot(mission_id, "expected", expected_state, refs)
        observed = self._snapshot(mission_id, "observed", observed_state, refs)
        findings = self.detect_drift(
            mission_id=mission_id,
            expected=expected_state,
            observed=observed_state,
            evidence_refs=refs,
        )
        checkpoint = ProductTwinCheckpoint(
            mission_id=mission_id,
            expected=expected,
            observed=observed,
            drift_findings=findings,
            reversible=reversible,
            rollback_ref=rollback_ref,
        )
        if self.store:
            self.store.save_record(
                checkpoint.checkpoint_id,
                "product_twin_checkpoint",
                checkpoint.model_dump(mode="json"),
                checkpoint.created_at,
                mission_id,
            )
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> ProductTwinCheckpoint | None:
        if not self.store:
            return None
        envelope = self.store.get_record_envelope(checkpoint_id)
        if not envelope:
            return None
        if envelope.get("record_type") != "product_twin_checkpoint":
            raise ValueError("product_twin_checkpoint_record_type_invalid")
        checkpoint = ProductTwinCheckpoint.model_validate(envelope["payload"])
        if (
            envelope.get("record_id") != checkpoint_id
            or checkpoint.checkpoint_id != checkpoint_id
            or envelope.get("mission_id") != checkpoint.mission_id
        ):
            raise ValueError("product_twin_checkpoint_integrity_invalid")
        return checkpoint

    def detect_drift(
        self,
        *,
        mission_id: str,
        expected: Any,
        observed: Any,
        evidence_refs: list[str] | None = None,
    ) -> list[DriftFinding]:
        refs = evidence_refs or []
        return [
            DriftFinding(
                mission_id=mission_id,
                drift_type=self._classify(path),
                path=path,
                expected=expected_value,
                observed=observed_value,
                severity=self._severity(path),
                evidence_refs=refs,
            )
            for path, expected_value, observed_value in self._diff(expected, observed)
        ]

    def _snapshot(
        self,
        mission_id: str,
        kind: str,
        state: dict[str, Any],
        evidence_refs: list[str],
    ) -> TwinSnapshot:
        encoded = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return TwinSnapshot(
            mission_id=mission_id,
            kind=kind,
            state=state,
            state_sha256=hashlib.sha256(encoded).hexdigest(),
            evidence_refs=evidence_refs,
        )

    def _diff(
        self,
        expected: Any,
        observed: Any,
        path: str = "$",
    ) -> list[tuple[str, DriftValue, DriftValue]]:
        findings: list[tuple[str, DriftValue, DriftValue]] = []

        if isinstance(expected, dict) and isinstance(observed, dict):
            for key in sorted(set(expected) | set(observed)):
                child_path = f"{path}.{key}"
                if key not in expected:
                    findings.append(
                        (child_path, DriftValue.missing(), DriftValue.present(observed[key]))
                    )
                elif key not in observed:
                    findings.append(
                        (child_path, DriftValue.present(expected[key]), DriftValue.missing())
                    )
                else:
                    findings.extend(self._diff(expected[key], observed[key], child_path))
            return findings

        if isinstance(expected, list) and isinstance(observed, list):
            common = min(len(expected), len(observed))
            for index in range(common):
                findings.extend(
                    self._diff(expected[index], observed[index], f"{path}[{index}]")
                )
            for index in range(common, len(expected)):
                findings.append(
                    (
                        f"{path}[{index}]",
                        DriftValue.present(expected[index]),
                        DriftValue.missing(),
                    )
                )
            for index in range(common, len(observed)):
                findings.append(
                    (
                        f"{path}[{index}]",
                        DriftValue.missing(),
                        DriftValue.present(observed[index]),
                    )
                )
            return findings

        if expected != observed:
            findings.append(
                (path, DriftValue.present(expected), DriftValue.present(observed))
            )
        return findings

    @staticmethod
    def _classify(path: str) -> DriftType:
        lowered = path.lower()
        if any(term in lowered for term in ("policy", "approval", "human_control", "authority")):
            return DriftType.POLICY_VIOLATION
        if any(term in lowered for term in ("evidence", "verification", "receipt")):
            return DriftType.EVIDENCE_GAP
        if any(term in lowered for term in ("accessibility", "voiceover", "reduce_motion", "focus")):
            return DriftType.ACCESSIBILITY_REGRESSION
        if any(term in lowered for term in ("metric", "kpi", "analytics")):
            return DriftType.METRIC_REGRESSION
        if any(term in lowered for term in ("design", "token", "component", "figma")):
            return DriftType.DESIGN_DRIFT
        if any(term in lowered for term in ("code", "swift", "web", "implementation")):
            return DriftType.CODE_DRIFT
        return DriftType.RUNTIME_DRIFT

    @staticmethod
    def _severity(path: str) -> RiskLevel:
        drift_type = ProductTwinEngine._classify(path)
        if drift_type == DriftType.POLICY_VIOLATION:
            return RiskLevel.R3
        if drift_type in (
            DriftType.EVIDENCE_GAP,
            DriftType.ACCESSIBILITY_REGRESSION,
            DriftType.RUNTIME_DRIFT,
        ):
            return RiskLevel.R2
        return RiskLevel.R1
