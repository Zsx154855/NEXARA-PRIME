"""DecisionFramework — structured decision-making with evidence weighting.

6-step process: Problem→Options→Evidence→Risk→Selection→Review.
"""

from __future__ import annotations

from ...models import new_id
from .models import Decision, DecisionOption, ConfidenceScore


class DecisionFramework:
    """Produces governed decisions with alternatives, evidence, and confidence."""

    name = "decision_framework"

    def decide(
        self,
        problem: str,
        options: list[DecisionOption],
        evidence: list[str] | None = None,
        risk_level: str = "R1",
        confidence: ConfidenceScore | None = None,
    ) -> Decision:
        """Evaluate options and select the best one based on evidence weighting."""
        evidence = evidence or []

        # Step 1-2: Problem is framed externally, options provided
        if not options:
            return Decision(
                decision_id=new_id("dec"),
                mission_id="",
                selected_option="none",
                reason="No options provided",
                evidence=evidence,
                risk=risk_level,
                confidence=0.0,
            )

        # Step 3: Evidence weighting — score each option
        scored = []
        for opt in options:
            evidence_count = len(opt.evidence)
            evidence_score = min(1.0, evidence_count / 3.0)
            confidence_factor = opt.confidence if opt.confidence > 0 else 0.5
            total = evidence_score * 0.6 + confidence_factor * 0.4
            scored.append((opt, total))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Step 4: Recommendation — top option
        best, best_score = scored[0]

        # Build reason
        reason_parts = [f"Selected: {best.description}"]
        reason_parts.append(f"Evidence strength: {len(best.evidence)} refs")
        reason_parts.append(f"Confidence: {best.confidence:.2f}")
        if len(scored) > 1:
            reason_parts.append(f"Alternatives: {len(scored) - 1} considered")

        # Step 5: Outcome prediction — use best option's predicted outcome
        # Step 6: Record — caller writes to DecisionMemory

        final_confidence = best_score if confidence is None else confidence.score

        return Decision(
            decision_id=new_id("dec"),
            mission_id="",
            selected_option=best.option_id,
            reason=" | ".join(reason_parts),
            evidence=best.evidence + evidence,
            risk=risk_level,
            confidence=round(final_confidence, 4),
            alternatives=options,
        )
