"""Read-only *contract check* for the existing bounded local report Mission.

This is a projection of Mission, Approval, Evidence, Tool, Event, Evaluation
and the on-disk report. It creates no new authority or trusted success state.

A CONTRACT_PASS is NOT an independently authenticated BUSINESS_SUCCESS.
In particular, a reviewer/auditor actor label cannot establish agent identity,
and the generic MissionCompiler criteria do not prove arbitrary user objectives.
Do not wire this checker directly as ExperienceStore.outcome_validator.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .evidence import EvidenceStore
from .governance import ApprovalEngine
from .models import ApprovalStatus, Mission, MissionState
from .state_machine import TRANSITIONS


# Exact criteria emitted by the existing root MissionCompiler. Do not
# silently reinterpret a user-edited or domain-specific WorkContract.
REPORT_CRITERIA = frozenset({
    "full state machine trace exists",
    "report is written only after approval",
    "verification and evidence are present",
    "evaluation passes safety and evidence gates",
})


@dataclass(frozen=True)
class ReportContractCheck:
    mission_id: str
    status: str  # CONTRACT_PASS | CONTRACT_FAIL | OUTCOME_UNKNOWN
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    # Deliberate: process acceptance != independently authenticated success.
    business_outcome_verified: bool = False


class ReportMissionContractVerifier:
    """Recompute four known process criteria using existing authorities.

    No DB writes or evidence creation are performed by this class. Be aware
    the canonical EvidenceStore.receipt_status() delegates to receipt-chain
    verification, which can repair evidence verification state in some cases.
    Run it in a bounded test DB if strictly zero mutations are required.
    """

    def __init__(
        self,
        *,
        store: Any,
        evidence: EvidenceStore,
        approvals: ApprovalEngine,
        report_root: Path,
    ) -> None:
        self._store = store
        self._evidence = evidence
        self._approvals = approvals
        self._report_root = Path(report_root)

    def _verified(self, evidence_id: Any, mission_id: str, kind: str):
        if not isinstance(evidence_id, str) or not evidence_id:
            return None
        if self._evidence.is_preverified_and_integrity_bound(evidence_id) is not True:
            return None
        obj = self._evidence.get_by_id(evidence_id)
        if obj.mission_id != mission_id or obj.kind != kind:
            return None
        return obj

    def evaluate(self, mission_id: str, verification_evidence_id: str) -> ReportContractCheck:
        checks = {
            "full state machine trace exists": False,
            "report is written only after approval": False,
            "verification and evidence are present": False,
            "evaluation passes safety and evidence gates": False,
        }
        failures: list[str] = []
        try:
            envelope = self._store.get_record_envelope(mission_id)
            if (
                not envelope or envelope.get("record_type") != "mission"
                or envelope.get("record_id") != mission_id
                or envelope.get("mission_id") != mission_id
            ):
                return ReportContractCheck(mission_id, "CONTRACT_FAIL", checks, ("mission_envelope_invalid",))
            mission = Mission.model_validate(envelope["payload"])
            if (
                mission.mission_id != mission_id
                or mission.spec.mission_id != mission_id
                or mission.contract is None
                or mission.contract.mission_id != mission_id
                or mission.contract.status != "approved"
                or set(mission.contract.acceptance_criteria) != REPORT_CRITERIA
                or set(mission.spec.acceptance_criteria) != REPORT_CRITERIA
            ):
                return ReportContractCheck(
                    mission_id, "OUTCOME_UNKNOWN", checks,
                    ("unsupported_or_unapproved_report_contract",),
                )
            result = mission.result
            if not isinstance(result, dict):
                return ReportContractCheck(mission_id, "CONTRACT_FAIL", checks, ("mission_result_missing",))

            # Criterion 1: verify actual persisted state events, their
            # transitions and their independently integrity-bound evidence.
            transitions = [
                e for e in self._store.list_events(mission_id)
                if e.get("event_type") == "mission.state_changed"
                and e.get("aggregate_id") == mission_id
            ]
            state = MissionState.INTENT
            event_ids: list[str] = []
            valid_trace = bool(transitions)
            for event in transitions:
                payload = event.get("payload") or {}
                try:
                    to_state = MissionState(payload.get("to"))
                    from_state = MissionState(payload.get("from"))
                except (TypeError, ValueError):
                    valid_trace = False
                    break
                if (
                    from_state != state
                    or to_state not in TRANSITIONS.get(state, set())
                    or event.get("trace_id") != mission.trace_id
                    or not event.get("event_id")
                ):
                    valid_trace = False
                    break
                event_ids.append(str(event["event_id"]))
                state = to_state
            state_evidence = self._evidence.list(mission_id)
            bound: dict[str, Any] = {}
            for item in state_evidence:
                if item.get("kind") != "state_transition":
                    continue
                artifact = self._verified(item.get("evidence_id"), mission_id, "state_transition")
                if (
                    artifact is not None
                    and artifact.actor == "state_machine"
                    and artifact.source == "mission.state_changed"
                    and artifact.source_event_id
                ):
                    bound[artifact.source_event_id] = artifact
            traces_bound = all(
                event["event_id"] in bound
                and bound[event["event_id"]].content == (
                    f"Mission {mission_id} transitioned from "
                    f"{event['payload']['from']} to {event['payload']['to']}."
                )
                for event in transitions
            ) if valid_trace else False
            checks["full state machine trace exists"] = (
                valid_trace
                and state == MissionState.COMPLETED
                and mission.state == MissionState.COMPLETED
                and bool(event_ids)
                and len(event_ids) == len(transitions)
                and len(event_ids) == len(set(event_ids))
                and traces_bound
            )
            if not checks["full state machine trace exists"]:
                failures.append("state_event_or_evidence_chain_invalid")

            # Verify actual output, canonical report root, persisted tool
            # invocation and the tool-written SHA; do not trust a report_path.
            expected = (self._report_root.resolve() / mission_id / "mission-report.md")
            report_path = Path(str(result.get("report_path", "")))
            file_ok = (
                bool(result.get("report_path"))
                and report_path.resolve() == expected.resolve()
                and expected.resolve().is_relative_to(self._report_root.resolve())
                and expected.is_file()
            )
            raw = expected.read_bytes() if file_ok else b""
            digest = hashlib.sha256(raw).hexdigest() if raw else ""
            tool_envelopes, corrupt = self._store.audit_record_envelopes("tool", mission_id)
            writers = [
                e["payload"] for e in tool_envelopes
                if e.get("record_type") == "tool"
                and e["payload"].get("tool_name") == "file_write_report"
            ]
            writer = writers[0] if len(writers) == 1 and not corrupt else {}
            write_ok = bool(
                writer
                and writer.get("mission_id") == mission_id
                and writer.get("trace_id") == mission.trace_id
                and writer.get("status") == "completed"
                and writer.get("idempotency_key") == f"{mission_id}:report-write"
                and writer.get("arguments", {}).get("path") == f"{mission_id}/mission-report.md"
                and writer.get("result", {}).get("path") == str(expected)
                and writer.get("result", {}).get("sha256") == digest
                and writer.get("result", {}).get("bytes") == len(raw)
                and hashlib.sha256(
                    str(writer.get("arguments", {}).get("content", "")).encode("utf-8")
                ).hexdigest() == digest
                and result.get("receipt_evidence_id") == writer.get("receipt_evidence_id")
                and mission.rollback_point == writer.get("invocation_id")
                and raw
            )

            approval_id = mission.pending_approval_id
            approval = self._approvals.get(approval_id) if approval_id else None
            approved = bool(
                approval and approval.mission_id == mission_id
                and approval.action == "file_write_report"
                and approval.approval_scope == "single_action"
                and approval.executor_id == "runtime"
                and approval.status == ApprovalStatus.CONSUMED
                and approval.decided_by and approval.decided_at
                and self._approvals.consumption_matches(
                    approval, actor_id="runtime", use_id=f"{mission_id}:report-write",
                )
            )
            if approved and writer:
                approved_at = datetime.fromisoformat(approval.decided_at)
                written_at = datetime.fromisoformat(writer["created_at"])
                approved = bool(approved_at <= written_at)
            checks["report is written only after approval"] = bool(file_ok and write_ok and approved)
            if not checks["report is written only after approval"]:
                failures.append("report_file_tool_or_approval_invalid")

            verification = self._verified(verification_evidence_id, mission_id, "verification_report")
            receipt = self._evidence.receipt_status(mission_id, tool_names=["file_write_report"])
            receipt_artifact = self._verified(result.get("receipt_evidence_id"), mission_id, "execution_receipt")
            verified_report = False
            if verification and receipt_artifact and file_ok and write_ok:
                report_json = json.loads(verification.content)
                verified_report = bool(
                    verification.actor == "reviewer"
                    and verification.evidence_id == result.get("verification_evidence_id")
                    and receipt_artifact.evidence_id in verification.parent_evidence
                    and report_json.get("exists") is True
                    and report_json.get("non_empty") is True
                    and report_json.get("bytes") == len(raw)
                    and report_json.get("sha256") == digest
                )
            # Re-compute verdict content and report checksum, not just actor labels.
            verdicts_ok = True
            for key, kind, actor in (
                ("reviewer_evidence_id", "reviewer_verdict", "reviewer"),
                ("auditor_evidence_id", "auditor_verdict", "auditor"),
            ):
                artifact = self._verified(result.get(key), mission_id, kind)
                if artifact is None or artifact.actor != actor:
                    verdicts_ok = False
                    break
                verdict = json.loads(artifact.content)
                if not (
                    isinstance(verdict, dict)
                    and verdict.get("actor") == actor
                    and verdict.get("mission_id") == mission_id
                    and verdict.get("passed") is True
                    and verdict.get("context_hash") == result.get("context_hash")
                ):
                    verdicts_ok = False
                    break
                if actor == "reviewer" and verdict.get("report_sha256") != digest:
                    verdicts_ok = False
                    break
            checks["verification and evidence are present"] = bool(
                verified_report and verdicts_ok and receipt.get("status") == "present"
                and receipt.get("chain_intact") is True
            )
            if not checks["verification and evidence are present"]:
                failures.append("verification_receipt_or_review_invalid")

            evaluation_id = result.get("evaluation_id")
            evaluation_envelope = (
                self._store.get_record_envelope(evaluation_id)
                if isinstance(evaluation_id, str) and evaluation_id else None
            )
            evaluation = (
                evaluation_envelope.get("payload", {})
                if evaluation_envelope
                and evaluation_envelope.get("record_type") == "evaluation"
                and evaluation_envelope.get("record_id") == evaluation_id
                and evaluation_envelope.get("mission_id") == mission_id
                else {}
            )
            checks["evaluation passes safety and evidence gates"] = bool(
                evaluation.get("mission_id") == mission_id
                and evaluation.get("evaluation_id") == evaluation_id
                and evaluation.get("passed") is True
                and result.get("evaluation_passed") is True
                and all(
                    isinstance(evaluation.get(k), (int, float))
                    and evaluation[k] >= 0.9
                    for k in ("correctness", "reliability", "safety", "evidence_coverage")
                )
            )
            if not checks["evaluation passes safety and evidence gates"]:
                failures.append("persisted_evaluation_gate_invalid")
            status = "CONTRACT_PASS" if all(checks.values()) else "CONTRACT_FAIL"
            return ReportContractCheck(mission_id, status, checks, tuple(failures))
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, AttributeError, json.JSONDecodeError):
            return ReportContractCheck(mission_id, "OUTCOME_UNKNOWN", checks, ("authoritative_recheck_unavailable",))
