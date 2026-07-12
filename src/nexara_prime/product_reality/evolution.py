from __future__ import annotations

from nexara_prime.models import RiskLevel

from .models import EvolutionProposal, EvolutionValidation, PromotionDecision


class EvolutionPromotionGate:
    """Policy gate for controlled product evolution.

    The gate never performs promotion. It returns a deterministic decision.
    R3/R4 changes require explicit human approval. R4 additionally requires
    manual release authorization.
    """

    def assess(
        self,
        proposal: EvolutionProposal,
        validation: EvolutionValidation,
    ) -> PromotionDecision:
        reasons: list[str] = []
        required_actions: list[str] = []

        if not validation.verification_passed:
            required_actions.append("complete verification")

        if proposal.risk_level != RiskLevel.R0 and not validation.simulation_passed:
            required_actions.append("complete simulation")

        if proposal.risk_level in (RiskLevel.R2, RiskLevel.R3, RiskLevel.R4):
            if not validation.accessibility_passed:
                required_actions.append("complete accessibility validation")
            if not validation.governance_passed:
                required_actions.append("complete governance validation")

        if proposal.risk_level in (RiskLevel.R3, RiskLevel.R4):
            if validation.human_approval_status != "approved":
                required_actions.append("obtain explicit human approval")

        if proposal.risk_level == RiskLevel.R4:
            if not validation.manual_release_authorized:
                required_actions.append("obtain manual release authorization")

        if required_actions:
            reasons.append(
                f"{proposal.risk_level.value} proposal is not eligible for promotion"
            )
            return PromotionDecision(
                proposal_id=proposal.proposal_id,
                allowed=False,
                reasons=reasons,
                required_actions=sorted(set(required_actions)),
            )

        reasons.append(
            f"{proposal.risk_level.value} proposal satisfies its promotion prerequisites"
        )
        return PromotionDecision(
            proposal_id=proposal.proposal_id,
            allowed=True,
            reasons=reasons,
        )
