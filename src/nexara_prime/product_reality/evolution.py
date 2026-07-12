from __future__ import annotations

from datetime import datetime, timezone

from nexara_prime.evidence import EvidenceStore
from nexara_prime.governance import ApprovalEngine
from nexara_prime.models import ApprovalRequest, ApprovalStatus, RiskLevel

from .models import EvolutionProposal, EvolutionValidation, PromotionDecision


class EvolutionPromotionGate:
    """Evidence-backed and approval-bound gate for controlled evolution.

    The gate never performs product promotion. It only assesses eligibility.
    Successful R3/R4 assessments consume their single-action stored approvals.
    """

    def __init__(self, approvals: ApprovalEngine, evidence: EvidenceStore):
        self.approvals = approvals
        self.evidence = evidence

    def assess(
        self,
        proposal: EvolutionProposal,
        validation: EvolutionValidation,
    ) -> PromotionDecision:
        required_actions: list[str] = []
        verified_evidence_refs: list[str] = []
        approvals_to_consume: list[ApprovalRequest] = []

        verified, evidence_errors = self._verify_evidence_refs(
            proposal.evidence_refs,
            mission_id=proposal.mission_id,
            purpose="promotion evidence",
        )
        verified_evidence_refs.extend(verified)
        required_actions.extend(evidence_errors)

        if not validation.verification_passed:
            required_actions.append("complete verification")

        if proposal.risk_level != RiskLevel.R0 and not validation.simulation_passed:
            required_actions.append("complete simulation")

        if proposal.risk_level in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
            if not validation.accessibility_passed:
                required_actions.append("complete accessibility validation")
            if not validation.governance_passed:
                required_actions.append("complete governance validation")

            rollback_verified, rollback_errors = self._verify_evidence_refs(
                proposal.rollback_evidence_refs,
                mission_id=proposal.mission_id,
                purpose="rollback evidence",
            )
            verified_evidence_refs.extend(rollback_verified)
            required_actions.extend(rollback_errors)

            if not proposal.rollback_plan:
                required_actions.append("provide rollback plan")
            if not proposal.rollback_checkpoint_id:
                required_actions.append("provide rollback checkpoint")

        if proposal.risk_level in (RiskLevel.R3, RiskLevel.R4):
            approval, approval_errors = self._validate_stored_approval(
                approval_id=validation.approval_id,
                proposal=proposal,
                actor_id=validation.actor_id,
                expected_action=proposal.promotion_action,
                purpose="promotion approval",
            )
            required_actions.extend(approval_errors)
            if approval:
                approvals_to_consume.append(approval)

        if proposal.risk_level == RiskLevel.R4:
            release_approval, release_errors = self._validate_stored_approval(
                approval_id=validation.release_approval_id,
                proposal=proposal,
                actor_id=validation.actor_id,
                expected_action=proposal.release_action,
                purpose="manual release approval",
            )
            required_actions.extend(release_errors)
            if release_approval:
                approvals_to_consume.append(release_approval)

        required_actions = sorted(set(required_actions))
        if required_actions:
            return PromotionDecision(
                proposal_id=proposal.proposal_id,
                allowed=False,
                reasons=[
                    f"{proposal.risk_level.value} proposal is not eligible for promotion"
                ],
                required_actions=required_actions,
                verified_evidence_refs=sorted(set(verified_evidence_refs)),
            )

        consumed_ids: list[str] = []
        for approval in approvals_to_consume:
            self._consume_single_action_approval(approval)
            consumed_ids.append(approval.approval_id)

        return PromotionDecision(
            proposal_id=proposal.proposal_id,
            allowed=True,
            reasons=[
                f"{proposal.risk_level.value} proposal satisfies evidence, recovery, governance, and approval prerequisites"
            ],
            verified_evidence_refs=sorted(set(verified_evidence_refs)),
            consumed_approval_ids=consumed_ids,
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
            raw = self.evidence.store.get_record(evidence_id)
            if not raw:
                errors.append(f"{purpose} not found: {evidence_id}")
                continue
            if raw.get("mission_id") != mission_id:
                errors.append(f"{purpose} mission mismatch: {evidence_id}")
                continue
            try:
                digest_valid = self.evidence.verify(evidence_id)
            except (KeyError, TypeError, ValueError):
                digest_valid = False
            if not digest_valid:
                errors.append(f"{purpose} failed digest verification: {evidence_id}")
                continue
            verified.append(evidence_id)

        return verified, errors

    def _validate_stored_approval(
        self,
        *,
        approval_id: str | None,
        proposal: EvolutionProposal,
        actor_id: str | None,
        expected_action: str,
        purpose: str,
    ) -> tuple[ApprovalRequest | None, list[str]]:
        if not approval_id:
            return None, [f"obtain stored {purpose}"]
        if not actor_id:
            return None, [f"identify executor for {purpose}"]

        approval = self.approvals.get(approval_id)
        if not approval:
            return None, [f"stored {purpose} not found"]
        if approval.status != ApprovalStatus.APPROVED:
            return None, [f"stored {purpose} is not approved"]
        if approval.mission_id != proposal.mission_id:
            return None, [f"stored {purpose} mission mismatch"]
        if approval.action != expected_action:
            return None, [f"stored {purpose} proposal scope mismatch"]
        if approval.approval_scope != "single_action":
            return None, [f"stored {purpose} must use single_action scope"]
        if approval.executor_id and approval.executor_id != actor_id:
            return None, [f"stored {purpose} executor mismatch"]
        if not approval.decided_by or not approval.decided_at:
            return None, [f"stored {purpose} has no human decision record"]
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

    def _consume_single_action_approval(self, approval: ApprovalRequest) -> None:
        approval.status = ApprovalStatus.CONSUMED
        self.approvals.store.save_record(
            approval.approval_id,
            "approval",
            approval.model_dump(mode="json"),
            approval.created_at,
            approval.mission_id,
        )
