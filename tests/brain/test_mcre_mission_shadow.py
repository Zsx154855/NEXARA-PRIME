"""M1 mission adapter tests: real code, synthetic Mission/EvidenceStore fixtures."""
import hashlib
import json
from enum import Enum
from types import SimpleNamespace

import pytest

from nexara_prime.brain.mcre_mission_shadow import MissionShadowObserver, ShadowSnapshot
from nexara_prime.brain.mcre_shadow import ContextRef


class Risk(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"


def mission(mid="m1", risk=Risk.R1, budget=None, usage=None):
    spec = SimpleNamespace(mission_id=mid, objective="Repair source issue", risk_level=risk)
    return SimpleNamespace(mission_id=mid, spec=spec, resource_budget=budget, budget_usage=usage)


def snapshot(**overrides):
    values = dict(project_id="NEXARA-PRIME", repo_sha="f4a5400d", environment_id="py312",
                  scope_id="tenant-a", observed_cost_usd=None)
    values.update(overrides)
    return ShadowSnapshot(**values)


def test_read_only_default_unknown_cost_never_authorizes():
    x = MissionShadowObserver().observe(mission(), snapshot())
    assert x.strategy == "RESEARCH"
    assert x.known_cost_usd is None
    assert x.shadow_only and not x.execution_authorized


def test_real_mission_r2_always_escalates_without_authority():
    x = MissionShadowObserver().observe(mission(risk=Risk.R2), snapshot())
    assert x.strategy == "ESCALATE" and not x.execution_authorized


def test_missing_source_version_is_not_reuse():
    x = MissionShadowObserver().observe(mission(), snapshot(repo_sha=None))
    assert x.strategy == "RESEARCH"


def test_mission_spec_identity_mismatch_rejected():
    m = mission()
    m.spec.mission_id = "other"
    with pytest.raises(ValueError, match="mission_spec_identity_mismatch"):
        MissionShadowObserver().observe(m, snapshot())


def test_no_counterfeit_token_balance_from_absent_usage():
    m = mission(budget={"token_budget": 1000, "mission_id": "m1"}, usage=None)
    assert MissionShadowObserver._budget(m) is None


def test_exhausted_existing_budget_defers():
    m = mission(budget={"token_budget": 100, "mission_id": "m1"},
                usage={"tokens_used": 110, "mission_id": "m1"})
    assert MissionShadowObserver().observe(m, snapshot()).strategy == "DEFER"


def test_false_boolean_budget_rejected_as_unknown():
    m = mission(budget={"token_budget": True}, usage={"tokens_used": 3})
    assert MissionShadowObserver._budget(m) is None


def test_cross_mission_budget_mismatch_unknown():
    m = mission(budget={"token_budget": 100, "mission_id": "other"},
                usage={"tokens_used": 20, "mission_id": "m1"})
    assert MissionShadowObserver._budget(m) is None


def test_repeat_failure_defer_without_changes_to_mission():
    m = mission()
    original = (m.mission_id, m.spec.objective)
    x = MissionShadowObserver().observe(m, snapshot(retries_without_new_evidence=2))
    assert x.strategy == "DEFER"
    assert original == (m.mission_id, m.spec.objective)


def test_observer_does_not_implicitly_read_or_write_evidence_without_refs():
    class Spy:
        def is_preverified_and_integrity_bound(self, eid):
            raise AssertionError("unexpected evidence read")
        def verify_artifact(self, eid):
            raise AssertionError("unexpected evidence read")
        def verify(self, eid):
            raise AssertionError("unexpected evidence mutation")
    assert MissionShadowObserver(Spy()).observe(mission(), snapshot()).strategy == "RESEARCH"


def test_unknown_but_reported_cost_not_set_to_zero():
    x = MissionShadowObserver().observe(mission(), snapshot(observed_cost_usd=0.01))
    assert x.known_cost_usd == 0.01


def test_cross_mission_equivalent_work_has_same_provisional_key():
    a = MissionShadowObserver().observe(mission(mid="m1"), snapshot())
    b = MissionShadowObserver().observe(mission(mid="m2"), snapshot())
    assert a.task_key == b.task_key
    assert not a.execution_authorized and not b.execution_authorized


def test_authoritative_evidence_manifest_reuse_only_in_exact_scope():
    obj = dict(project_id="NEXARA-PRIME", repo_sha="f4a5400d",
               environment_id="py312", scope_id="tenant-a")
    content = json.dumps(obj)
    digest = hashlib.sha256(content.encode()).hexdigest()
    ref = ContextRef("ev1", **obj, content_digest=digest)
    artifact = SimpleNamespace(evidence_id="ev1", kind="mcre_context", content=content,
                               verification_status="verified")
    class Reader:
        def is_preverified_and_integrity_bound(self, eid):
            return eid == "ev1"
        def verify_artifact(self, eid):
            return artifact
    obs = MissionShadowObserver(Reader())
    assert obs.observe(mission(), snapshot(context_refs=(ref,))).strategy == "REUSE"
    assert obs.observe(mission(), snapshot(context_refs=(ref,), scope_id="tenant-b")).strategy == "RESEARCH"


def test_exhausted_mission_budget_not_overridden_by_snapshot():
    m = mission(budget={"token_budget": 100, "mission_id": "m1", "budget_id": "b1"},
                usage={"tokens_used": 100, "mission_id": "m1", "budget_id": "b1"})
    assert MissionShadowObserver().observe(m, snapshot(remaining_tokens=500)).strategy == "DEFER"


def test_mismatched_budget_identity_is_unknown():
    m = mission(budget={"token_budget": 100, "mission_id": "m1", "budget_id": "a"},
                usage={"tokens_used": 80, "mission_id": "m1", "budget_id": "b"})
    assert MissionShadowObserver._budget(m) is None
