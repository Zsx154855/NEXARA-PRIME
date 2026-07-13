from __future__ import annotations

from datetime import datetime, timezone

from nexara_prime.evidence import EvidenceStore
from nexara_prime.governance import ApprovalEngine
from nexara_prime.models import ApprovalRequest, ApprovalStatus, RiskLevel

from .models import (
    EvolutionProposal,
    EvolutionValidation,
    ProductTwinCheckpoint,
    PromotionDecision,
)


class EvolutionPromotionGate:
    """Evidence-backed and approval-bound gate for controlled evolution."""

    def __init__(
        self,
        approvals: ApprovalEngine,
        evidence: EvidenceStore,
        *,
        authorized_human_principals: set[str] | None = None,
    ):
        self.approvals = approvals
        self.evidence = evidence
        self.authorized_human_principals = frozenset(
            authorized_human_principals or set()
        )

    def assess(
        self,
        proposal: EvolutionProposal,
        validation: EvolutionValidation,
    ) -> PromotionDecision:
        required_actions: list[str] = []
        verified_evidence_refs: list[str] = []
        approvals_to_consume: list[ApprovalRequest] = []

        verified, errors = self._verify_evidence_refs(
            proposal.evidence_refs,
            mission_id=proposal.mission_id,
            purpose="promotion evidence",
        )
        verified_evidence_refs.extend(verified)
        required_actions.extend(errors)

        if not validation.verification_passed:
            required_actions.append("complete verification")
        if proposal.risk_level != RiskLevel.R0 and not validation.simulation_passed:
            required_actions.append("complete simulation")

        if proposal.risk_level in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
            if not validation.accessibility_passed:
                required_actions.append("complete accessibility validation")
            if not validation.governance_passed:
                required_actions.append("complete governance validation")

            verified, errors = self._verify_evidence_refs(
                proposal.rollback_evidence_refs,
                mission_id=proposal.mission_id,
                purpose="rollback evidence",
            )
            verified_evidence_refs.extend(verified)
            required_actions.extend(errors)
            required_actions.extend(self._validate_checkpoint(proposal))

        if proposal.risk_level in (RiskLevel.R3, RiskLevel.R4):
            approval, errors = self._validate_stored_approval(
                approval_id=validation.approval_id,
                proposal=proposal,
                actor_id=validation.actor_id,
                expected_action=proposal.promotion_action,
                expected_risk=proposal.risk_level,
                purpose="promotion approval",
            )
            required_actions.extend(errors)
            if approval:
                approvals_to_consume.append(approval)

        if proposal.risk_level == RiskLevel.R4:
            approval, errors = self._validate_stored_approval(
                approval_id=validation.release_approval_id,
                proposal=proposal,
                actor_id=validation.actor_id,
                expected_action=proposal.release_action,
                expected_risk=RiskLevel.R4,
                purpose="manual release approval",
            )
            required_actions.extend(errors)
            if approval:
                approvals_to_consume.append(approval)

        required_actions = sorted(set(required_actions))
        if required_actions:
            return PromotionDecision(
                proposal_id=proposal.proposal_id,
                allowed=False,
                reasons=[f"{proposal.risk_level.value} proposal is not eligible for promotion"],
                required_actions=required_actions,
                verified_evidence_refs=sorted(set(verified_evidence_refs)),
            )

        if not self._consume_approvals_atomically(approvals_to_consume):
            return PromotionDecision(
                proposal_id=proposal.proposal_id,
                allowed=False,
                reasons=["approval consumption conflict"],
                required_actions=["obtain fresh stored approval records"],
                verified_evidence_refs=sorted(set(verified_evidence_refs)),
            )

        return PromotionDecision(
            proposal_id=proposal.proposal_id,
            allowed=True,
            reasons=[
                f"{proposal.risk_level.value} proposal satisfies evidence, recovery, governance, and approval prerequisites"
            ],
            verified_evidence_refs=sorted(set(verified_evidence_refs)),
            consumed_approval_ids=[item.approval_id for item in approvals_to_consume],
        )

    def _verify_evidence_refs(
        self,
        refs: list[str],
        *,
        mission_id: str,
        purpose: str,
    ) -> tuple[list[str], list[str]]:
        verified: list[str] = []
        errors: list[str] = []
        if not refs:
            return verified, [f"provide {purpose}"]

        for evidence_id in refs:
            envelope = self.evidence.store.get_record_envelope(evidence_id)
            if not envelope or envelope.get("record_type") != "evidence":
                errors.append(f"{purpose} integrity envelope invalid: {evidence_id}")
                continue
            if envelope.get("mission_id") != mission_id:
                errors.append(f"{purpose} mission mismatch: {evidence_id}")
                continue
            raw = envelope["payload"]
            if raw.get("mission_id") != mission_id:
                errors.append(f"{purpose} payload mission mismatch: {evidence_id}")
                continue
            if raw.get("verification_status") != "verified":
                errors.append(f"{purpose} is not pre-verified: {evidence_id}")
                continue
            if not self.evidence.is_preverified_and_integrity_bound(evidence_id):
                errors.append(
                    f"{purpose} failed digest verification or envelope verification: {evidence_id}"
                )
                continue
            verified.append(evidence_id)
        return verified, errors

    def _validate_checkpoint(self, proposal: EvolutionProposal) -> list[str]:
        if not proposal.rollback_plan:
            return ["provide rollback plan"]
        if not proposal.rollback_checkpoint_id:
            return ["provide rollback checkpoint"]
        envelope = self.approvals.store.get_record_envelope(
            proposal.rollback_checkpoint_id
        )
        if not envelope or envelope.get("record_type") != "product_twin_checkpoint":
            return ["stored rollback checkpoint not found or integrity invalid"]
        try:
            checkpoint = ProductTwinCheckpoint.model_validate(envelope["payload"])
        except (TypeError, ValueError):
            return ["stored rollback checkpoint is invalid"]
        errors: list[str] = []
        if envelope.get("mission_id") != proposal.mission_id:
            errors.append("stored rollback checkpoint mission mismatch")
        if checkpoint.mission_id != proposal.mission_id:
            errors.append("stored rollback checkpoint payload mission mismatch")
        if not checkpoint.reversible:
            errors.append("stored rollback checkpoint is not reversible")
        return errors

    def _validate_stored_approval(
        self,
        *,
        approval_id: str | None,
        proposal: EvolutionProposal,
        actor_id: str | None,
        expected_action: str,
        expected_risk: RiskLevel,
        purpose: str,
    ) -> tuple[ApprovalRequest | None, list[str]]:
        if not approval_id:
            return None, [f"obtain stored {purpose}"]
        if not actor_id:
            return None, [f"identify executor for {purpose}"]

        envelope = self.approvals.store.get_record_envelope(approval_id)
        if not envelope or envelope.get("record_type") != "approval":
            return None, [f"stored {purpose} integrity envelope invalid"]
        if envelope.get("mission_id") != proposal.mission_id:
            return None, [f"stored {purpose} mission mismatch"]

        try:
            approval = ApprovalRequest.model_validate(envelope["payload"])
        except (TypeError, ValueError):
            return None, [f"stored {purpose} is invalid"]
        if approval.status != ApprovalStatus.APPROVED:
            return None, [f"stored {purpose} is not approved"]
        if approval.mission_id != proposal.mission_id:
            return None, [f"stored {purpose} payload mission mismatch"]
        if approval.action != expected_action:
            return None, [f"stored {purpose} proposal scope mismatch"]
        if approval.risk_level != expected_risk:
            return None, [f"stored {purpose} risk mismatch"]
        if approval.approval_scope != "single_action":
            return None, [f"stored {purpose} must use single_action scope"]
        if not approval.executor_id:
            return None, [f"stored {purpose} has no executor binding"]
        if approval.executor_id != actor_id:
            return None, [f"stored {purpose} executor mismatch"]
        if not approval.decided_by or not approval.decided_at:
            return None, [f"stored {purpose} has no human decision record"]
        if approval.decided_by not in self.authorized_human_principals:
            return None, [f"stored {purpose} was not decided by an authorized human"]
        if not self._approval_is_unexpired(approval):
            return None, [f"stored {purpose} is expired or has invalid expiry"]
        return approval, []

    @staticmethod
    def _approval_is_unexpired(approval: ApprovalRequest) -> bool:
        if not approval.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(approval.expires_at)
        except (TypeError, ValueError):
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > datetime.now(timezone.utc)

    def _consume_approvals_atomically(self, approvals: list[ApprovalRequest]) -> bool:
        return self.approvals.store.compare_and_set_record_fields_atomically(
            [
                {
                    "record_id": approval.approval_id,
                    "record_type": "approval",
                    "field": "status",
                    "expected_value": ApprovalStatus.APPROVED.value,
                    "new_value": ApprovalStatus.CONSUMED.value,
                }
                for approval in approvals
            ]
        )
