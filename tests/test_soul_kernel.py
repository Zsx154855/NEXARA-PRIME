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

    experience = soul.record_experience(
        "PR review exposed a governance gap",
        "Technical checks are not governance approval",
        "Separate technical pass from governance pass",
        ["evidence:pr-review"],
        source_type="failure",
        owner_approval_id="approval:test-001",
    )
    assert experience.evidence_refs == ("evidence:pr-review",)
    assert "Separate technical pass from governance pass" in soul.snapshot()["learned_character"]
    assert soul.narrative().failures == ("PR review exposed a governance gap",)
    assert soul.expression is SoulExpression.GROWTH


def test_learned_character_requires_owner_approval_and_core_is_immutable() -> None:
    soul = SoulKernel(owner_id="owner-1")
    with pytest.raises(PermissionError, match="owner_approval"):
        soul.apply_learned_character("new trait", ["ev:1"], approved_by="other")
    soul.apply_learned_character("new trait", ["ev:1"], approved_by="owner-1")
    assert "new trait" in soul.snapshot()["learned_character"]
    with pytest.raises(PermissionError, match="immutable_core"):
        soul.attempt_core_change("truth", "appeasement")


def test_decision_uses_moral_order_and_records_tradeoff() -> None:
    soul = SoulKernel()
    decision = soul.decide_conflict(
        {
            "ship_now": (MoralValue.COMPLETION, MoralValue.SPEED),
            "verify_first": (MoralValue.TRUTH, MoralValue.SAFETY),
        },
        ["ev:decision-1"],
    )
    assert decision.selected_option == "verify_first"
    assert decision.protected_values[0] is MoralValue.SAFETY
    assert decision.requires_owner_confirmation is True
    assert "speed" in decision.tradeoffs


def test_restraint_fails_closed() -> None:
    soul = SoulKernel()
    assert soul.assess_restraint("write", [], authorized=True).disposition is SoulDisposition.ASK
    assert soul.assess_restraint("write", ["ev:1"], authorized=False).disposition is SoulDisposition.ASK
    assert soul.assess_restraint("delete", ["ev:1"], authorized=True, risk_level="R4").disposition is SoulDisposition.ESCALATE
    assert soul.assess_restraint("inspect", [], authorized=False, observe_only=True).disposition is SoulDisposition.OBSERVE_ONLY
    assert soul.assess_restraint("nothing", [], authorized=False, no_op=True).disposition is SoulDisposition.NO_OP


def test_expression_contract_and_rituals_are_deterministic_projections() -> None:
    soul = SoulKernel()
    soul.acknowledge_limitation("provider evidence is unavailable", ["ev:limit"])
    assert soul.expression_contract()["core"] == "contracted"
    assert soul.identity_fingerprint == soul.identity_fingerprint
    assert soul.daily_wake().ritual == "daily_wake"
    assert soul.task_complete().message.startswith("这项工作已经完成")
    assert soul.weekly_review().ritual == "weekly_review"


def test_chief_brain_exposes_soul_health() -> None:
    brain = ChiefBrainKernel()
    health = brain.health()
    assert health["soul"]["constitution"] == "NEXARA_SOUL_CONSTITUTION_V1"
    assert health["soul"]["integrity"] is True
