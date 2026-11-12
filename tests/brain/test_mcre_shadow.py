import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mcre_shadow", ROOT / "src/nexara_prime/brain/mcre_shadow.py")
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)
ContextRef, DecisionRequest, MCREShadow = module.ContextRef, module.DecisionRequest, module.MCREShadow


def request(**overrides):
    data = dict(mission_id="m1", project_id="NEXARA-PRIME", objective="Fix issue", repo_sha="abc123",
                environment_id="py312", scope_id="tenant-a")
    data.update(overrides)
    return DecisionRequest(**data)


def ref(**overrides):
    data = dict(evidence_id="ev1", project_id="NEXARA-PRIME", repo_sha="abc123",
                environment_id="py312", scope_id="tenant-a", content_digest="sha256:abc")
    data.update(overrides)
    return ContextRef(**data)


def test_no_resolver_cannot_reuse_and_never_authorizes():
    x = MCREShadow().advise(request(), (ref(),))
    assert x.strategy == "RESEARCH"
    assert x.shadow_only and not x.execution_authorized


def test_exact_verified_context_reuse():
    x = MCREShadow(lambda evidence: evidence.evidence_id == "ev1").advise(request(), (ref(),))
    assert x.strategy == "REUSE" and x.evidence_ids == ("ev1",)


@pytest.mark.parametrize("changes", [dict(repo_sha="other"), dict(project_id="UNSEEN"),
                                    dict(environment_id="py39"), dict(scope_id="tenant-b"),
                                    dict(content_digest="")])
def test_stale_or_cross_scope_evidence_rejected(changes):
    x = MCREShadow(lambda _: True).advise(request(), (ref(**changes),))
    assert x.strategy == "RESEARCH" and x.evidence_ids == ()


def test_recovery_stop_on_repeated_failure_without_evidence():
    assert MCREShadow().advise(request(retries_without_new_evidence=2)).strategy == "DEFER"


def test_risk_cannot_turn_into_authority():
    x = MCREShadow(lambda _: True).advise(request(risk_level="R3"), (ref(),))
    assert x.strategy == "ESCALATE" and not x.execution_authorized


def test_unknown_source_fails_closed_for_reuse():
    assert MCREShadow(lambda _: True).advise(request(repo_sha=None), (ref(),)).strategy == "RESEARCH"


def test_unknown_cost_not_falsified_into_zero():
    x = MCREShadow().advise(request())
    assert x.known_cost_usd is None
    assert "COST_UNKNOWN" in x.reason_codes
    assert "nexara.mcre.observed_cost_usd" not in x.otel_attributes()


def test_deterministic_task_key_scoped_by_repo_and_project():
    a = MCREShadow.task_key(request(mission_id="m1"))
    assert a == MCREShadow.task_key(request(mission_id="m2"))
    assert a != MCREShadow.task_key(request(project_id="OTHER"))
    assert a != MCREShadow.task_key(request(repo_sha="other"))


def test_budget_exhaustion_defers():
    assert MCREShadow().advise(request(remaining_tokens=0)).strategy == "DEFER"


def test_evidence_verifier_exception_fails_closed():
    def broken(_):
        raise RuntimeError("store offline")
    assert MCREShadow(broken).advise(request(), (ref(),)).strategy == "RESEARCH"


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        MCREShadow().advise(request(remaining_tokens=-1))
