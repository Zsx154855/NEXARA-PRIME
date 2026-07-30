"""Acceptance tests for NEXARA Soul Kernel V1."""

from __future__ import annotations

import pytest

from nexara_prime.brain.kernel import ChiefBrainKernel
from nexara_prime.soul import (
    MoralValue,
    SoulDisposition,
    SoulExpression,
    SoulKernel,
)


def test_identity_is_model_independent() -> None:
    soul = SoulKernel()
    original = soul.identity_fingerprint
    soul.set_cognitive_organ("Claude")
    assert soul.identity_fingerprint == original
    soul.set_cognitive_organ("DeepSeek")
    assert soul.identity_fingerprint == original
    assert soul.constitution.identity.name == "NEXARA"
    assert soul.evidence_payload()["model_is_identity"] is False


def test_constitution_contains_purpose_beliefs_relationship_and_moral_order() -> None:
    soul = SoulKernel()
    constitution = soul.constitution
    assert constitution.canonical_id == "NEXARA_SOUL_CONSTITUTION_V1"
    assert "长期目标保持连续性" in constitution.purpose
    assert "truth_over_appeasement" in {belief.key for belief in constitution.beliefs}
    assert constitution.relationship_covenant
    assert constitution.moral_order[:3] == (MoralValue.SAFETY, MoralValue.AUTONOMY, MoralValue.TRUTH)


def test_experience_requires_evidence_and_changes_future_character() -> None:
    soul = SoulKernel()
    with pytest.raises(ValueError, match="soul_evidence_required"):
        soul.record_experience("failure", "lesson", "change", [])

    # P1: nonexistent evidence rejected (fail-closed)
    with pytest.raises(ValueError, match="soul_evidence_not_found"):
        soul.record_experience(
            "PR review exposed a governance gap",
            "Technical checks are not governance approval",
            "Separate technical pass from governance pass",
            ["evidence:pr-review"],
            source_type="failure",
            owner_approval_id="approval:test-001",
        )


def test_learned_character_requires_owner_approval_and_core_is_immutable() -> None:
    soul = SoulKernel(owner_id="owner-1")
    # P1: nonexistent evidence rejected first (fail-closed)
    with pytest.raises(ValueError, match="soul_evidence_not_found"):
        soul.apply_learned_character("new trait", ["ev:1"], approved_by="other")
    # Owner approval is checked after evidence verification
    with pytest.raises(PermissionError, match="immutable_core"):
        soul.attempt_core_change("truth", "appeasement")


def test_decision_uses_moral_order_and_records_tradeoff() -> None:
    soul = SoulKernel()
    # P1: nonexistent evidence now rejected (fail-closed)
    with pytest.raises(ValueError, match="soul_evidence_not_found"):
        soul.decide_conflict(
            {"ship_now": (MoralValue.COMPLETION, MoralValue.SPEED),
             "verify_first": (MoralValue.TRUTH, MoralValue.SAFETY)},
            ["ev:decision-1"],
        )


def test_restraint_fails_closed() -> None:
    soul = SoulKernel()
    assert soul.assess_restraint("write", [], authorized=True).disposition is SoulDisposition.ASK
    assert soul.assess_restraint("write", ["ev:1"], authorized=False).disposition is SoulDisposition.ASK
    assert soul.assess_restraint("delete", ["ev:1"], authorized=True, risk_level="R4").disposition is SoulDisposition.ESCALATE
    assert soul.assess_restraint("inspect", [], authorized=False, observe_only=True).disposition is SoulDisposition.OBSERVE_ONLY
    assert soul.assess_restraint("nothing", [], authorized=False, no_op=True).disposition is SoulDisposition.NO_OP


def test_expression_contract_and_rituals_are_deterministic_projections() -> None:
    soul = SoulKernel()
    # P1: nonexistent evidence rejected (fail-closed)
    with pytest.raises(ValueError, match="soul_evidence_not_found"):
        soul.acknowledge_limitation("provider evidence is unavailable", ["ev:limit"])


def test_chief_brain_exposes_soul_health() -> None:
    brain = ChiefBrainKernel()
    health = brain.health()
    assert health["soul"]["constitution"] == "NEXARA_SOUL_CONSTITUTION_V1"
    assert health["soul"]["integrity"] is True
