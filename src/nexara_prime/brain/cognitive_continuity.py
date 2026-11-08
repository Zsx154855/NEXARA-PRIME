"""Opt-in Cognitive State + Goal Loop + Evidence-Gated Learning bootstrap.

No model calls, tool execution, permission grants or production state mutations.
Records use the repository's canonical SQLiteStore integrity envelopes; verified
EvidenceStore artifacts are required before any proposal is durable. A goal is
an ADVISORY candidate for existing Kernel admission, never executable authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class DurableRecords(Protocol):
    def list_record_envelopes(self, record_type: str, mission_id: str | None = None) -> list[dict[str, Any]]: ...
    def get_record_envelope(self, record_id: str) -> dict[str, Any] | None: ...
    def save_record_if_absent(self, record_id: str, record_type: str, payload: dict[str, Any],
                              created_at: str, mission_id: str | None = None) -> bool: ...


class VerifiedEvidence(Protocol):
    def is_preverified_and_integrity_bound(self, evidence_id: str) -> bool: ...
    def get_by_id(self, evidence_id: str) -> Any: ...


class ContinuityError(ValueError):
    """Cognitive state integrity, evidence, or permission boundary failure."""


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _valid_texts(items: Any) -> list[str]:
    if not isinstance(items, list) or len(items) > 100:
        raise ContinuityError("invalid_state_items")
    if any(not isinstance(s, str) or not s.strip() or len(s) > 2000 for s in items):
        raise ContinuityError("invalid_state_text")
    return list(items)


@dataclass(frozen=True)
class CognitiveState:
    project_id: str
    revision: int
    identity: str
    owner_goals: tuple[str, ...]
    beliefs: tuple[str, ...]
    uncertainties: tuple[str, ...]
    commitments: tuple[str, ...]
    hypotheses: tuple[str, ...]
    last_evidence_id: str = ""
    anchor: str = ""


class CognitiveStateStore:
    """Immutable, chained revisions; no automatic edits of identity/owner goals.

    Optimistic concurrency uses one deterministic record id per revision and
    SQLiteStore.save_record_if_absent's database-atomic insert. Detect forks,
    gaps, missing origin anchors and tampered records on every load.
    """

    _type = "cognitive_state_v1"
    _owner_fields = frozenset({"identity", "owner_goals", "beliefs", "commitments"})
    _agent_fields = frozenset({"hypotheses", "uncertainties"})

    def __init__(self, records: DurableRecords, evidence: VerifiedEvidence, project_id: str,
                 owner_authorizer: Callable[[str], bool] | None = None):
        self._owner_authorizer = owner_authorizer
        if not project_id or len(project_id) > 128:
            raise ContinuityError("invalid_project")
        self.records, self.evidence, self.project_id = records, evidence, project_id
        self._prefix = _digest(project_id)[:24]

    def load(self) -> CognitiveState:
        rows = self.records.list_record_envelopes(self._type, self.project_id)
        rows.sort(key=lambda x: x["payload"].get("revision", -1))
        state = CognitiveState(self.project_id, 0, "NEXARA-PRIME cognitive core",
                               (), (), (), (), ())
        for row in rows:
            payload = row["payload"]
            revision = state.revision + 1
            expected_id = f"cogstate_{self._prefix}_{revision}"
            if (row["record_id"] != expected_id or row["record_type"] != self._type
                or row["mission_id"] != self.project_id
                or payload.get("revision") != revision
                or payload.get("parent_anchor", "") != state.anchor
                or row.get("origin_sha256") != row.get("integrity_sha256")):
                raise ContinuityError("cognitive_state_chain_invalid")
            data = payload.get("state")
            if not isinstance(data, dict) or data.get("project_id") != self.project_id:
                raise ContinuityError("cognitive_state_payload_invalid")
            state = CognitiveState(self.project_id, revision,
                                   data["identity"], tuple(data["owner_goals"]),
                                   tuple(data["beliefs"]), tuple(data["uncertainties"]),
                                   tuple(data["commitments"]), tuple(data["hypotheses"]),
                                   payload["evidence_id"], row["integrity_sha256"])
        return state

    def update(self, *, expected_revision: int, actor: str, changes: dict[str, Any],
               evidence_id: str) -> CognitiveState:
        if not evidence_id or not self.evidence.is_preverified_and_integrity_bound(evidence_id):
            raise ContinuityError("verified_evidence_required")
        if actor not in {"owner", "agent"} or not isinstance(changes, dict) or not changes:
            raise ContinuityError("invalid_actor_or_changes")
        allowed = self._owner_fields | self._agent_fields if actor == "owner" else self._agent_fields
        if any(key not in allowed for key in changes):
            raise ContinuityError("state_permission_denied")
        if actor == "owner" and (self._owner_authorizer is None or not self._owner_authorizer(evidence_id)):
            raise ContinuityError("trusted_owner_authorization_required")
        before = self.load()
        if before.revision != expected_revision:
            raise ContinuityError("stale_cognitive_revision")
        data = {
            "project_id": self.project_id, "identity": before.identity,
            "owner_goals": list(before.owner_goals), "beliefs": list(before.beliefs),
            "uncertainties": list(before.uncertainties), "commitments": list(before.commitments),
            "hypotheses": list(before.hypotheses),
        }
        for key, value in changes.items():
            if key == "identity":
                if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                    raise ContinuityError("invalid_identity")
                data[key] = value
            else:
                data[key] = _valid_texts(value)
        payload = {"revision": expected_revision + 1, "parent_anchor": before.anchor,
                   "state": data, "evidence_id": evidence_id, "actor": actor}
        record_id = f"cogstate_{self._prefix}_{expected_revision + 1}"
        if not self.records.save_record_if_absent(record_id, self._type, payload, _timestamp(), self.project_id):
            raise ContinuityError("concurrent_cognitive_update")
        return self.load()


class AutonomousGoalLoop:
    """Turn existing SignalAnalyzer observations into bounded audit proposals.

    It never executes a mission, changes permissions, or invents evidence. An
    external, separately governed Kernel must decide admission and execution.
    """

    _type = "cognitive_goal_proposal_v1"
    _approved_signals = {"fix_failing_tests": "Investigate verified failing tests (read-only)",
                         "audit_recent_changes": "Audit verified recent file changes (read-only)"}

    def __init__(self, records: DurableRecords, evidence: VerifiedEvidence, project_id: str,
                 event_authorizer: Callable[[str, str, str], bool] | None = None):
        self.records, self.evidence, self.project_id = records, evidence, project_id
        # A verified content hash is not an authenticated observation. The
        # caller must inject a trusted, project-scoped event provenance check.
        self._event_authorizer = event_authorizer

    def tick(self, events: list[Any], evidence_by_event: dict[str, str]) -> list[dict[str, Any]]:
        if self._event_authorizer is None:
            # No authenticated observer, no durable autonomous proposals.
            return []
        from .environment.intelligence import SignalAnalyzer
        suggestions = SignalAnalyzer().analyze(events)
        output: list[dict[str, Any]] = []
        for suggestion in suggestions:
            goal_type = suggestion.get("mission")
            if goal_type not in self._approved_signals:
                continue
            event_ids = list(suggestion.get("evidence", []))
            if not event_ids or len(event_ids) != len(set(event_ids)):
                continue
            refs = [evidence_by_event.get(eid, "") for eid in event_ids]
            if (not all(refs) or len(set(refs)) != len(refs)
                or not all(self.evidence.is_preverified_and_integrity_bound(ref) for ref in refs)):
                continue
            # A verified but unrelated artifact is not proof of this event.
            if any(self.evidence.get_by_id(ref).source_event_id != eid
                   for eid, ref in zip(event_ids, refs)):
                continue
            if not all(self._event_authorizer(self.project_id, eid, ref)
                       for eid, ref in zip(event_ids, refs)):
                continue
            fingerprint = _digest({"project": self.project_id, "type": goal_type,
                                   "event_ids": sorted(event_ids)})
            record_id = f"coggoal_{fingerprint[:32]}"
            payload = {"proposal_id": record_id, "project_id": self.project_id,
                       "objective": self._approved_signals[goal_type], "source": goal_type,
                       "risk_level": "R0", "cost_limit": 0, "status": "PROPOSED",
                       "event_ids": sorted(event_ids), "evidence_refs": refs,
                       "execution_authorized": False}
            inserted = self.records.save_record_if_absent(
                record_id, self._type, payload, _timestamp(), self.project_id)
            row = self.records.get_record_envelope(record_id)
            if not row or row["payload"] != payload or row["record_type"] != self._type:
                raise ContinuityError("goal_proposal_integrity_conflict")
            output.append({**payload, "new": inserted})
        return output

    def list_proposals(self) -> list[dict[str, Any]]:
        return [r["payload"] for r in self.records.list_record_envelopes(self._type, self.project_id)]


class EvidenceGatedLearning:
    """Promote nothing automatically; persist independently verified suggestions.

    Metrics are parsed from verified evidence payloads, not claimed by the
    caller. Passing makes a candidate REVIEWABLE, not an active policy or skill.
    """

    _type = "cognitive_learning_candidate_v1"

    def __init__(self, records: DurableRecords, evidence: VerifiedEvidence, project_id: str,
                 auditor_authorizer: Callable[[str], bool] | None = None):
        self.records, self.evidence, self.project_id = records, evidence, project_id
        self._auditor_authorizer = auditor_authorizer

    def evaluate(self, *, mission_id: str, strategy: str, baseline_id: str,
                 candidate_id: str, executor_id: str, auditor_id: str) -> dict[str, Any]:
        if (not mission_id or not strategy or len(strategy) > 2000
            or not baseline_id or not candidate_id or baseline_id == candidate_id
            or not executor_id or not auditor_id or executor_id == auditor_id):
            raise ContinuityError("independent_evidence_required")
        if self._auditor_authorizer is None or not self._auditor_authorizer(auditor_id):
            raise ContinuityError("trusted_auditor_authorization_required")
        for eid in (baseline_id, candidate_id):
            if not self.evidence.is_preverified_and_integrity_bound(eid):
                raise ContinuityError("verified_evidence_required")
        baseline = self.evidence.get_by_id(baseline_id)
        candidate = self.evidence.get_by_id(candidate_id)
        if (baseline.mission_id != mission_id or candidate.mission_id != mission_id
            or baseline.actor != auditor_id or candidate.actor != auditor_id):
            raise ContinuityError("evaluator_identity_or_mission_mismatch")

        def metrics(artifact: Any) -> dict[str, int]:
            try:
                obj = json.loads(artifact.content)
                keys = ("tests_passed", "tests_failed", "tokens")
                if not isinstance(obj, dict) or any(type(obj.get(k)) is not int or obj[k] < 0 for k in keys):
                    raise ValueError("invalid_metrics")
                suite_id = obj.get("suite_id")
                if not isinstance(suite_id, str) or not suite_id.strip() or len(suite_id) > 200:
                    raise ValueError("missing_comparable_test_suite")
                return {**{key: obj[key] for key in keys}, "suite_id": suite_id}
            except (TypeError, ValueError, KeyError) as exc:
                raise ContinuityError("verified_metrics_invalid") from exc

        before, after = metrics(baseline), metrics(candidate)
        passing = (before["suite_id"] == after["suite_id"]
                   and before["tests_passed"] > 0
                   and before["tests_failed"] == 0 and after["tests_failed"] == 0
                   and after["tests_passed"] >= before["tests_passed"]
                   and after["tokens"] < before["tokens"])
        payload = {"project_id": self.project_id, "mission_id": mission_id,
                   "strategy": strategy, "baseline_evidence": baseline_id,
                   "candidate_evidence": candidate_id, "executor_id": executor_id,
                   "auditor_id": auditor_id, "baseline": before, "candidate": after,
                   "status": "REVIEWABLE" if passing else "REJECTED",
                   "activated": False, "permission_granted": False}
        record_id = f"coglearn_{_digest(payload)[:32]}"
        inserted = self.records.save_record_if_absent(
            record_id, self._type, payload, _timestamp(), self.project_id)
        row = self.records.get_record_envelope(record_id)
        if not row or row["payload"] != payload or row["record_type"] != self._type:
            raise ContinuityError("learning_candidate_integrity_conflict")
        return {"candidate_id": record_id, **payload, "new": inserted}

    def list_candidates(self) -> list[dict[str, Any]]:
        return [r["payload"] for r in self.records.list_record_envelopes(self._type, self.project_id)]
