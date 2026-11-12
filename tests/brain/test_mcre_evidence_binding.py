"""Fixture-only adapter contract tests; NOT actual SQLite EvidenceStore E2E."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "src"))
# Import package requiring no production services.
from nexara_prime.brain.mcre_shadow import ContextRef
from nexara_prime.brain.verified_skill_evolution import Trial
from nexara_prime.brain.mcre_evidence_binding import EvidenceStoreBinding


class Reader:
    def __init__(self, artifact, preverified=True):
        self.artifact = artifact
        self.preverified = preverified
        self.calls = []

    def is_preverified_and_integrity_bound(self, evidence_id):
        self.calls.append("is_preverified_and_integrity_bound")
        return self.preverified

    def verify_artifact(self, evidence_id):
        self.calls.append("verify_artifact")
        return self.artifact


def context():
    payload = dict(project_id="NEXARA-PRIME", repo_sha="abc123",
                   environment_id="py312", scope_id="tenant-a")
    content = json.dumps(payload, sort_keys=True)
    art = SimpleNamespace(evidence_id="ev1", kind="mcre_context",
                          verification_status="verified", content=content)
    ref = ContextRef("ev1", "NEXARA-PRIME", "abc123", "py312", "tenant-a",
                     hashlib.sha256(content.encode()).hexdigest())
    return art, ref


def trial():
    data = dict(task_id="holdout-0", variant="treatment", passed=True,
                turns=4, reviewer_id="independent-qa", input_tokens=80, cost_usd=0.0)
    art = SimpleNamespace(evidence_id="ev1", kind="skill_eval_trial",
                          verification_status="verified", content=json.dumps(data),
                          task_id="holdout-0", actor="independent-qa")
    t = Trial("holdout-0", "treatment", True, 4, "ev1", "independent-qa", 80, 0.0)
    return art, t


def test_verified_context_manifest():
    art, ref = context()
    reader = Reader(art)
    assert EvidenceStoreBinding(reader).verify_context(ref)
    assert reader.calls == ["is_preverified_and_integrity_bound", "verify_artifact"]


def test_context_fails_if_origin_unverified():
    art, ref = context()
    reader = Reader(art, preverified=False)
    assert not EvidenceStoreBinding(reader).verify_context(ref)
    assert reader.calls == ["is_preverified_and_integrity_bound"]


def test_context_digest_tamper_rejected():
    art, ref = context()
    tampered = ContextRef(ref.evidence_id, ref.project_id, ref.repo_sha,
                          ref.environment_id, ref.scope_id, "0" * 64)
    assert not EvidenceStoreBinding(Reader(art)).verify_context(tampered)


def test_context_project_mismatch_rejected():
    art, ref = context()
    changed = ContextRef(ref.evidence_id, "UNSEEN", ref.repo_sha,
                         ref.environment_id, ref.scope_id, ref.content_digest)
    assert not EvidenceStoreBinding(Reader(art)).verify_context(changed)


def test_valid_trial_binding():
    art, t = trial()
    assert EvidenceStoreBinding(Reader(art)).verify_trial(t)


def test_forged_trial_result_cannot_reuse_other_receipt():
    art, t = trial()
    changed = Trial(t.task_id, t.variant, False, 2, t.evidence_id, t.reviewer_id, 10, 0.0)
    assert not EvidenceStoreBinding(Reader(art)).verify_trial(changed)


def test_trial_actor_mismatch_rejected():
    art, t = trial()
    art.actor = "author"
    assert not EvidenceStoreBinding(Reader(art)).verify_trial(t)


def test_trial_bool_type_confusion_rejected():
    art, t = trial()
    data = json.loads(art.content)
    data["passed"] = 1
    art.content = json.dumps(data)
    assert not EvidenceStoreBinding(Reader(art)).verify_trial(t)


def test_trial_unverified_status_rejected():
    art, t = trial()
    art.verification_status = "unverified"
    assert not EvidenceStoreBinding(Reader(art)).verify_trial(t)
