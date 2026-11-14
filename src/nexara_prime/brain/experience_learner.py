"""ExperienceLearner — records mission outcomes, extracts patterns, ranks experiences.

Trusted admission (task-2):
- action experiences and lessons require authentic, mission-bound evidence;
- the canonical EvidenceStore path also requires the experience content to be
  consistent with a verifiable receipt (tool receipt or experience receipt);
- caller-asserted ``verification_status="verified"`` is not sufficient unless the
  EvidenceStore produced a verification transition event or the creating actor is
  explicitly allowlisted by the assembly path;
- rejected admissions are counted/logged without mission ids or evidence content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from ..models import new_id, now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController
    from ..evidence import EvidenceStore

_log = logging.getLogger("nexara_prime.brain.experience_learner")

# Coarse trust boundary: actors whose direct "verified" evidence is admissible.
# This is NOT an identity proof; a real verifier identity/authz layer is still
# required before production trust in multi-tenant or adversarial settings.
TRUSTED_VERIFIER_ACTORS: frozenset[str] = frozenset({
    "tool_runtime",
    "reviewer",
    "auditor",
    "verification_engine",
})

_TOOL_STATUS_SUCCESS: dict[str, bool] = {"completed": True, "failed": False}

# Conservative decision policy: no recommendation from a single sample or a
# known-failing action.
_MIN_DECISION_SAMPLES = 2
_MIN_DECISION_SUCCESS_RATE = 0.5


def _read_only_evidence_validator(
    evidence_store: EvidenceStore,
    trusted_actors: frozenset[str],
) -> Callable[[str, str], bool]:
    """Read-only authenticity check over the canonical EvidenceStore."""

    def _check(mission_id: str, evidence_id: str) -> bool:
        if not mission_id or not evidence_id:
            return False
        if evidence_store.is_trusted_verified(
            evidence_id, trusted_actors=trusted_actors
        ) is not True:
            return False
        return evidence_store.get_by_id(evidence_id).mission_id == mission_id

    return _check


@dataclass
class ExperienceRecord:
    mission_id: str
    outcome: str
    action: str
    result: str
    success: bool
    evidence_id: str
    patterns: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    confidence: float = 0.5
    trace_id: str = ""
    created_at: str = ""
    evidence_sha256: str = ""
    evidence_kind: str = ""
    result_sha256: str = ""


@dataclass
class Pattern:
    pattern_id: str
    pattern_type: str
    description: str
    frequency: int
    success_rate: float
    confidence: float
    examples: list[str] = field(default_factory=list)


class ExperienceLearner:
    """Records mission outcomes, extracts patterns, ranks experiences safely."""

    def __init__(
        self,
        memory_controller: MemoryController,
        *,
        evidence_store: EvidenceStore | None = None,
        evidence_validator: Callable[[str, str], bool] | None = None,
        trusted_verifier_actors: frozenset[str] | None = None,
        allow_test_seam: bool = False,
    ) -> None:
        self._mc = memory_controller
        self._store = evidence_store
        self._seam = evidence_validator is not None and allow_test_seam
        if evidence_validator is not None and not allow_test_seam:
            raise ValueError("evidence_validator_requires_allow_test_seam")
        self._trusted_actors = (
            TRUSTED_VERIFIER_ACTORS
            if trusted_verifier_actors is None
            else frozenset(trusted_verifier_actors)
        )
        if evidence_validator is not None:
            self._validator: Callable[[str, str], bool] | None = evidence_validator
        elif evidence_store is not None:
            self._validator = _read_only_evidence_validator(
                evidence_store, self._trusted_actors
            )
        else:
            self._validator = None
        self._rejections: Counter[str] = Counter()
        self._logged_reasons: set[str] = set()

    # ── Observability (no mission ids, evidence ids or content in logs) ──

    def rejection_stats(self) -> dict[str, int]:
        return dict(self._rejections)

    def _reject(self, reason: str) -> None:
        self._rejections[reason] += 1
        if reason not in self._logged_reasons:
            self._logged_reasons.add(reason)
            _log.warning(
                "experience_rejected reason=%s count=%d",
                reason,
                self._rejections[reason],
            )

    def _evidence_is_authentic(self, mission_id: str, evidence_id: str) -> bool:
        """Fail closed on missing verifier, missing ids or verifier errors."""
        if not mission_id or not evidence_id:
            self._reject("missing_evidence_ids")
            return False
        if self._validator is None:
            self._reject("no_verifier")
            return False
        try:
            ok = bool(self._validator(mission_id, evidence_id))
        except Exception:
            self._reject("verifier_error")
            return False
        if not ok:
            self._reject("evidence_untrusted")
        return ok

    # ── Receipt consistency (canonical EvidenceStore path only) ──

    def _receipt_for(
        self,
        mission_id: str,
        evidence_id: str,
        action: str,
        result: str,
        success: bool,
    ) -> dict[str, str]:
        if self._store is None:
            return {}
        artifact = self._store.get_by_id(evidence_id)
        if artifact.mission_id != mission_id:
            raise ValueError("experience_evidence_cross_mission")
        try:
            receipt = json.loads(artifact.content)
        except (TypeError, ValueError) as exc:
            raise ValueError("experience_evidence_receipt_invalid") from exc
        if not isinstance(receipt, dict):
            raise ValueError("experience_evidence_receipt_invalid")
        if artifact.kind not in {"execution_receipt", "experience_receipt"}:
            raise ValueError("experience_receipt_kind_unsupported")
        if artifact.kind == "execution_receipt":
            if (
                receipt.get("mission_id") != mission_id
                or receipt.get("tool_name") != action
            ):
                raise ValueError("experience_receipt_action_mismatch")
            mapped = _TOOL_STATUS_SUCCESS.get(str(receipt.get("status")))
            if mapped is None or mapped != success:
                raise ValueError("experience_receipt_status_mismatch")
            summary = receipt.get("result_summary")
            if summary is not None and str(summary) != result:
                raise ValueError("experience_receipt_result_mismatch")
        else:
            if (
                receipt.get("mission_id") != mission_id
                or receipt.get("action") != action
                or receipt.get("result") != result
                or receipt.get("success") is not success
            ):
                raise ValueError("experience_receipt_mismatch")
        binding = {
            "evidence_sha256": artifact.sha256,
            "evidence_kind": artifact.kind,
        }
        if artifact.kind == "execution_receipt":
            binding["result_sha256"] = hashlib.sha256(
                json.dumps(
                    receipt.get("result", {}), sort_keys=True, default=str
                ).encode("utf-8")
            ).hexdigest()
        return binding

    def _receipt_matches(self, record: dict[str, Any], data: dict[str, Any]) -> bool:
        if self._store is None:
            return self._seam  # explicit, flagged test seam only
        stored_sha = str(data.get("evidence_sha256") or "")
        if not stored_sha:
            self._reject("receipt_digest_missing")
            return False
        evidence_id = str(record.get("evidence_id", ""))
        try:
            artifact = self._store.get_by_id(evidence_id)
            if artifact.sha256 != stored_sha:
                self._reject("receipt_digest_mismatch")
                return False
            if artifact.kind != str(data.get("evidence_kind", "")):
                return False
            self._receipt_for(
                str(record.get("mission_id", "")),
                evidence_id,
                str(data.get("action", "")),
                str(data.get("result", "")),
                bool(data.get("success")),
            )
            if str(data.get("evidence_kind", "")) == "execution_receipt":
                stored_result = str(data.get("result_sha256") or "")
                if not stored_result:
                    return False
                receipt = json.loads(artifact.content)
                actual = hashlib.sha256(
                    json.dumps(
                        receipt.get("result", {}), sort_keys=True, default=str
                    ).encode("utf-8")
                ).hexdigest()
                if actual != stored_result:
                    return False
        except Exception:
            self._reject("receipt_validation_error")
            return False
        return True

    @staticmethod
    def _relevant(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop zero-relevance rows from the real controller; keep legacy mocks."""
        kept = []
        for record in records:
            if "relevance" in record and float(record.get("relevance") or 0.0) <= 0.0:
                continue
            kept.append(record)
        return kept

    # ── Idempotency (single-writer best effort) ──

    def _db(self):
        return getattr(self._mc, "_db", None)

    def _existing_experience_id(
        self, mission_id: str, evidence_id: str, action: str, success: bool,
        outcome: str, result: str,
    ) -> str | None:
        db = self._db()
        if db is None:
            return None
        for row in db.recall(mission_id=mission_id, kind="experience"):
            try:
                data = json.loads(row.get("content", "{}"))
            except (TypeError, ValueError):
                continue
            if (
                isinstance(data, dict)
                and data.get("evidence_id") == evidence_id
                and data.get("action") == action
                and data.get("success") is success
            ):
                if data.get("outcome") != outcome or data.get("result") != result:
                    raise ValueError("experience_idempotency_conflict")
                return str(row.get("memory_id", "")) or None
        return None

    def _existing_lesson_id(
        self, mission_id: str, evidence_id: str, lesson: str
    ) -> str | None:
        db = self._db()
        if db is None:
            return None
        for row in db.recall(mission_id=mission_id, kind="lesson"):
            try:
                data = json.loads(row.get("content", "{}"))
            except (TypeError, ValueError):
                continue
            if (
                isinstance(data, dict)
                and data.get("lesson") == lesson
                and row.get("evidence_id") == evidence_id
            ):
                return str(row.get("memory_id", "")) or None
        return None

    # ── Write paths ──

    def record_outcome(
        self, mission_id: str, outcome: str, action: str, result: str,
        success: bool, evidence_id: str | None = None, trace_id: str = "",
    ) -> str:
        if not evidence_id:
            self._reject("missing_evidence")
            raise ValueError(
                "memory_evidence_required: kind=experience requires evidence_id"
            )
        if not self._evidence_is_authentic(mission_id, evidence_id):
            raise ValueError(
                "experience_evidence_unverified: "
                f"mission_id={mission_id} evidence_id={evidence_id}"
            )
        try:
            binding = self._receipt_for(
                mission_id, evidence_id, action, result, success
            )
        except Exception as exc:
            reason = str(exc).strip() or "receipt_mismatch"
            self._reject(reason)
            raise ValueError(f"experience_receipt_invalid: {exc}") from exc
        try:
            existing = self._existing_experience_id(
                mission_id, evidence_id, action, success, outcome, result
            )
        except ValueError:
            self._reject("idempotency_conflict")
            raise
        if existing:
            return existing
        exp = ExperienceRecord(
            mission_id=mission_id, outcome=outcome, action=action,
            result=result, success=success, evidence_id=evidence_id,
            trace_id=trace_id, created_at=now_iso(), confidence=0.5,
            evidence_sha256=binding.get("evidence_sha256", ""),
            evidence_kind=binding.get("evidence_kind", ""),
            result_sha256=binding.get("result_sha256", ""),
        )
        content = self._serialize_exp(exp)
        confidence = 0.5 if success else 0.3
        key = f"exp:{mission_id}:{evidence_id}"
        db = self._db()
        memory_id = new_id("mem")
        if db is not None and hasattr(db, "insert_memory_with_idempotency"):
            payload_sha = hashlib.sha256(
                json.dumps(
                    {
                        "mission_id": mission_id,
                        "key": key,
                        "kind": "experience",
                        "evidence_id": evidence_id,
                        "action": action,
                        "outcome": outcome,
                        "result": result,
                        "success": success,
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            try:
                return self._mc.commit(
                    mission_id=mission_id, key=key, content=content,
                    kind="experience", evidence_id=evidence_id,
                    confidence=confidence, memory_id=memory_id,
                    idempotency_key=key,
                    idempotency_payload_sha256=payload_sha,
                )
            except ValueError as exc:
                if "idempotency_conflict" in str(exc):
                    self._reject("idempotency_conflict")
                    raise ValueError("experience_idempotency_conflict") from exc
                raise
        return self._mc.commit(
            mission_id=mission_id, key=key, content=content,
            kind="experience", evidence_id=evidence_id, confidence=confidence,
            memory_id=memory_id,
        )

    def record_lesson(self, mission_id: str, lesson: str, evidence_id: str | None = None) -> str:
        if not evidence_id:
            self._reject("missing_evidence")
            raise ValueError(
                "memory_evidence_required: kind=lesson requires evidence_id"
            )
        if not self._evidence_is_authentic(mission_id, evidence_id):
            raise ValueError(
                "lesson_evidence_unverified: "
                f"mission_id={mission_id} evidence_id={evidence_id}"
            )
        existing = self._existing_lesson_id(mission_id, evidence_id, lesson)
        if existing:
            return existing
        payload: dict[str, str] = {"lesson": lesson, "created_at": now_iso()}
        if self._store is not None:
            try:
                payload["evidence_sha256"] = self._store.get_by_id(evidence_id).sha256
            except Exception as exc:
                self._reject("lesson_digest_unavailable")
                raise ValueError("lesson_evidence_digest_unavailable") from exc
        lesson_slug = hashlib.sha256(lesson.encode("utf-8")).hexdigest()[:12]
        key = f"lesson:{mission_id}:{evidence_id}:{lesson_slug}"
        content = json.dumps(payload)
        payload_sha = hashlib.sha256(
            json.dumps(
                {
                    "mission_id": mission_id, "key": key, "kind": "lesson",
                    "evidence_id": evidence_id, "lesson": lesson,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        try:
            return self._mc.commit(
                mission_id=mission_id, key=key, content=content,
                kind="lesson", evidence_id=evidence_id, confidence=0.5,
                idempotency_key=key, idempotency_payload_sha256=payload_sha,
            )
        except ValueError as exc:
            if "idempotency_conflict" in str(exc):
                self._reject("idempotency_conflict")
                raise ValueError("lesson_idempotency_conflict") from exc
            raise

    # ── Read paths (must stay read-only and re-verify per row) ──

    def extract_patterns(self, limit: int = 50) -> list[Pattern]:
        records = self._relevant(self._mc.rank_retrieve(
            query="exp:", top_k=limit, layers=["semantic"], min_confidence=0.1,
            record_access=False,
        ))
        action_results: dict[str, list[bool]] = {}
        for r in records:
            data = self._action_payload(r)
            if data is None:
                continue
            action = data["action"]
            action_results.setdefault(action, []).append(data.get("success", False))

        patterns: list[Pattern] = []
        for action, results in action_results.items():
            if len(results) < 3:
                continue
            rate = sum(1 for r in results if r) / len(results)
            ptype = "tool_selection_success" if rate > 0.7 else "decision_path_outcome" if rate < 0.3 else "timing_pattern"
            patterns.append(Pattern(
                pattern_id=f"pat_{new_id('pat')}", pattern_type=ptype,
                description=f"Action '{action}': {rate:.0%} success ({len(results)} samples)",
                frequency=len(results), success_rate=rate,
                confidence=min(1.0, len(results) / 10.0),
            ))
        return sorted(patterns, key=lambda p: p.confidence * p.success_rate, reverse=True)

    def rank_experiences(self, keywords: str, top_k: int = 10) -> list[ExperienceRecord]:
        records = self._relevant(self._mc.rank_retrieve(
            query=keywords, top_k=top_k * 10, layers=["semantic"],
            min_confidence=0.1, record_access=False,
        ))
        exps: list[ExperienceRecord] = []
        for r in records:
            if self._action_payload(r) is not None:
                exp = self._deserialize_exp(r)
                if exp:
                    exp.confidence *= 1.0 + (0.1 if exp.success else -0.05)
                    exp.confidence = max(0.1, min(1.0, exp.confidence))
                    exps.append(exp)
        return sorted(exps, key=lambda e: e.confidence * (1.5 if e.success else 0.5), reverse=True)[:top_k]

    def recommend_action(self, keywords: str, top_k: int = 20) -> dict[str, Any]:
        """Recommend an action from verified experiences (decision use, not just recall).

        Uses only rows that pass recall admission (authentic evidence, receipt
        consistency, active lifecycle). Returns provenance so a caller can audit
        which experiences influenced the choice. Cold start returns action=None.
        """
        records = self.rank_experiences(keywords, top_k=top_k)
        stats: dict[str, dict[str, Any]] = {}
        for record in records:
            entry = stats.setdefault(
                record.action, {"successes": 0, "total": 0, "evidence_ids": []}
            )
            entry["total"] += 1
            if record.success:
                entry["successes"] += 1
            if record.evidence_id and record.evidence_id not in entry["evidence_ids"]:
                entry["evidence_ids"].append(record.evidence_id)
        if not stats:
            return {
                "action": None,
                "confidence": 0.0,
                "based_on": 0,
                "evidence_ids": [],
            }
        ranked = sorted(
            stats.items(),
            key=lambda item: (
                item[1]["successes"] / max(item[1]["total"], 1),
                item[1]["total"],
                item[0],
            ),
            reverse=True,
        )
        for action, entry in ranked:
            rate = round(entry["successes"] / max(entry["total"], 1), 4)
            if entry["total"] < _MIN_DECISION_SAMPLES:
                continue
            if rate < _MIN_DECISION_SUCCESS_RATE:
                continue
            return {
                "action": action,
                "confidence": rate,
                "based_on": entry["total"],
                "evidence_ids": entry["evidence_ids"][:3],
            }
        max_total = max((entry["total"] for entry in stats.values()), default=0)
        return {
            "action": None,
            "confidence": 0.0,
            "based_on": 0,
            "evidence_ids": [],
            "reason": (
                "insufficient_evidence"
                if max_total < _MIN_DECISION_SAMPLES
                else "low_success_rate"
            ),
        }

    def get_lessons(self, query: str = "", top_k: int = 10) -> list[str]:
        records = self._relevant(self._mc.rank_retrieve(
            query=query or "lesson", top_k=top_k, layers=["procedural"],
            min_confidence=0.1, record_access=False,
        ))
        lessons: list[str] = []
        for r in records:
            if r.get("kind") != "lesson" or not str(r.get("key", "")).startswith("lesson:"):
                continue
            if not self._evidence_is_authentic(
                str(r.get("mission_id", "")), str(r.get("evidence_id", ""))
            ):
                continue
            data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
            if self._store is not None:
                digest = str(data.get("evidence_sha256") or "")
                if not digest:
                    self._reject("lesson_digest_missing")
                    continue
                try:
                    artifact = self._store.get_by_id(str(r.get("evidence_id", "")))
                except Exception:
                    self._reject("lesson_digest_mismatch")
                    continue
                if artifact.sha256 != digest:
                    self._reject("lesson_digest_mismatch")
                    continue
            lessons.append(data.get("lesson", ""))
        return [x for x in lessons if x]

    def count_low_confidence(self, threshold: float = 0.2) -> int:
        records = self._relevant(self._mc.rank_retrieve(
            query="exp:", top_k=200, layers=["semantic"], min_confidence=0.0,
            record_access=False,
        ))
        return sum(1 for r in records if self._action_payload(r) is not None and float(r.get("confidence", 0.5)) < threshold)

    def summarize(self) -> dict[str, Any]:
        patterns = self.extract_patterns(limit=20)
        return {"patterns_found": len(patterns), "top_patterns": [(p.description, p.success_rate) for p in patterns[:5]], "success_actions": len([p for p in patterns if p.success_rate > 0.7]), "failure_actions": len([p for p in patterns if p.success_rate < 0.3])}

    def _action_payload(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """Return a trusted action payload or None."""
        data = self._shape_action_payload(record)
        if data is None:
            return None
        if not self._evidence_is_authentic(
            str(record.get("mission_id", "")),
            str(record.get("evidence_id", "")),
        ):
            return None
        if not self._receipt_matches(record, data):
            self._reject("receipt_mismatch")
            return None
        return data

    @staticmethod
    def _shape_action_payload(record: dict[str, Any]) -> dict[str, Any] | None:
        """Shape-only contract: action-level experience vs N01 mission summary."""
        if record.get("kind") != "experience":
            return None
        if not str(record.get("key", "")).startswith("exp:"):
            return None
        try:
            value = record.get("content", "{}")
            data = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        if not all(k in data for k in ("mission_id", "outcome", "action", "result", "success", "evidence_id")):
            return None
        if not isinstance(data["success"], bool) or not isinstance(data["action"], str) or not data["action"]:
            return None
        if data["mission_id"] != record.get("mission_id"):
            return None
        if data["evidence_id"] != record.get("evidence_id") or not data["evidence_id"]:
            return None
        return data

    @staticmethod
    def _serialize_exp(exp: ExperienceRecord) -> str:
        return json.dumps({
            "mission_id": exp.mission_id, "outcome": exp.outcome,
            "action": exp.action, "result": exp.result, "success": exp.success,
            "evidence_id": exp.evidence_id, "patterns": exp.patterns,
            "lessons": exp.lessons, "confidence": exp.confidence,
            "trace_id": exp.trace_id, "created_at": exp.created_at,
            "evidence_sha256": exp.evidence_sha256,
            "evidence_kind": exp.evidence_kind,
            "result_sha256": exp.result_sha256,
        })

    @staticmethod
    def _deserialize_exp(record: dict) -> ExperienceRecord | None:
        try:
            data = json.loads(record.get("content", "{}")) if isinstance(record.get("content"), str) else record.get("content", {})
            return ExperienceRecord(
                mission_id=data.get("mission_id", ""), outcome=data.get("outcome", ""),
                action=data.get("action", ""), result=data.get("result", ""),
                success=data.get("success", False), evidence_id=data.get("evidence_id", ""),
                patterns=data.get("patterns", []), lessons=data.get("lessons", []),
                confidence=float(data.get("confidence", 0.5)), trace_id=data.get("trace_id", ""),
                created_at=data.get("created_at", ""),
                evidence_sha256=data.get("evidence_sha256", ""),
                evidence_kind=data.get("evidence_kind", ""),
                result_sha256=data.get("result_sha256", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return None
