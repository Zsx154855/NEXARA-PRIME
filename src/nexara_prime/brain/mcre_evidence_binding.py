"""Read-only adapter for the existing EvidenceStore public integrity API.

This is a content-binding contract, NOT proof of authentic host identity or
source truth; neither grants operation/skill activation authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Protocol

from .mcre_shadow import ContextRef
from .verified_skill_evolution import Trial


class EvidenceReader(Protocol):
    def is_preverified_and_integrity_bound(self, evidence_id: str) -> bool: ...
    def verify_artifact(self, evidence_id: str) -> Any: ...


class EvidenceStoreBinding:
    """Bind MCRE references and evaluation rows to verified stored payloads.

    Expects the existing EvidenceStore; does not call its mutating verify().
    Caller must separately establish issuer/project authorization and real
    repository revision validity. All failures return False.
    """

    def __init__(self, evidence: EvidenceReader) -> None:
        self._evidence = evidence

    def _load(self, evidence_id: str, kind: str) -> tuple[Any, dict[str, Any]] | None:
        try:
            if not self._evidence.is_preverified_and_integrity_bound(evidence_id):
                return None
            artifact = self._evidence.verify_artifact(evidence_id)
            if (artifact.evidence_id != evidence_id or artifact.kind != kind
                    or artifact.verification_status != "verified" or not isinstance(artifact.content, str)):
                return None
            payload = json.loads(artifact.content)
            if not isinstance(payload, dict):
                return None
            return artifact, payload
        except (ValueError, KeyError, TypeError, AttributeError, RuntimeError):
            return None

    def verify_context(self, ref: ContextRef) -> bool:
        loaded = self._load(ref.evidence_id, "mcre_context")
        if loaded is None:
            return False
        artifact, payload = loaded
        digest = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(digest, ref.content_digest):
            return False
        return all(payload.get(key) == getattr(ref, key) and isinstance(payload.get(key), str)
                   for key in ("project_id", "repo_sha", "environment_id", "scope_id"))

    def verify_trial(self, trial: Trial) -> bool:
        loaded = self._load(trial.evidence_id, "skill_eval_trial")
        if loaded is None:
            return False
        artifact, payload = loaded
        if artifact.task_id != trial.task_id or artifact.actor != trial.reviewer_id:
            return False
        if not (type(payload.get("passed")) is bool and type(payload.get("turns")) is int):
            return False
        if payload.get("input_tokens") is not None and type(payload.get("input_tokens")) is not int:
            return False
        if payload.get("cost_usd") is not None and type(payload.get("cost_usd")) not in (int, float):
            return False
        return all(payload.get(field) == getattr(trial, field)
                   for field in ("task_id", "variant", "passed", "turns", "reviewer_id", "input_tokens", "cost_usd"))
