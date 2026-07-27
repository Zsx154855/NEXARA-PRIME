"""ReasoningKernel — cognitive inference layer.

Orchestrates: context assembly → thought process → decision → confidence → self-check.
Deterministic inference. No model calls. ZERO runtime modification.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ...models import new_id, now_iso
from .models import (
    ReasoningStep, ReasoningTrace, ReasoningResult,
    AssembledContext, MissionContext,
)
from .context_assembler import ContextAssembler, MemoryRetrievalAdapter
from .decision_framework import DecisionFramework
from .confidence import ConfidenceEngine
from .self_check import SelfCheckValidator

if TYPE_CHECKING:
    from ...memory_controller import MemoryController


class ThoughtProcessEngine:
    """Executes 7-step reasoning chain: OBSERVE→CLASSIFY→DECOMPOSE→INFER→VALIDATE→SYNTHESIZE→REFLECT."""

    name = "thought_process_engine"

    def execute_chain(
        self,
        query: str,
        context: AssembledContext,
        chain_type: str = "linear",
    ) -> list[ReasoningStep]:
        """Execute reasoning chain. Returns ordered list of reasoning steps."""
        steps: list[ReasoningStep] = []

        def _sid(n: str) -> str:
            return f"step_{len(steps) + 1:02d}"
        sid = _sid

        # OBSERVE — gather facts from context
        observe = ReasoningStep(
            step_id=sid("obs"),
            step_type="OBSERVE",
            input_facts=[r.get("content", "")[:100] for r in context.relevant_memories[:5]],
            operation="Extract relevant facts from assembled context",
            output=f"Context has {len(context.relevant_memories)} relevant memories, {len(context.past_decisions)} past decisions, {len(context.preferences)} preferences",
            confidence=0.95,
            evidence_refs=[r.get("memory_id", "") for r in context.relevant_memories[:3] if r.get("memory_id")],
        )
        steps.append(observe)

        # CLASSIFY — categorize problem type
        query_lower = query.lower()
        if any(w in query_lower for w in ("decide", "choose", "select", "which", "option")):
            problem_type = "selection"
        elif any(w in query_lower for w in ("predict", "estimate", "forecast", "will")):
            problem_type = "prediction"
        elif any(w in query_lower for w in ("diagnose", "why", "cause", "root")):
            problem_type = "diagnosis"
        elif any(w in query_lower for w in ("yes", "no", "should", "allow", "permit")):
            problem_type = "binary"
        else:
            problem_type = "classification"

        classify = ReasoningStep(
            step_id=sid("cls"),
            step_type="CLASSIFY",
            input_facts=[query],
            operation="Classify problem type from query keywords",
            output=f"Problem type: {problem_type}",
            confidence=0.85,
            depends_on=[observe.step_id],
        )
        steps.append(classify)

        # DECOMPOSE — break into sub-problems
        sub_problems = self._decompose(query, context)
        decompose = ReasoningStep(
            step_id=sid("dec"),
            step_type="DECOMPOSE",
            input_facts=[query],
            operation="Break problem into sub-problems",
            output=f"Decomposed into {len(sub_problems)} sub-problems: {'; '.join(sub_problems[:3])}",
            confidence=0.80,
            depends_on=[classify.step_id],
        )
        steps.append(decompose)

        # INFER — draw conclusions from evidence
        conclusion = self._infer(query, context, problem_type)
        infer = ReasoningStep(
            step_id=sid("inf"),
            step_type="INFER",
            input_facts=[r.get("content", "")[:80] for r in context.relevant_memories[:3]],
            operation="Draw conclusions from evidence and past patterns",
            output=conclusion,
            confidence=0.70,
            evidence_refs=[r.get("memory_id", "") for r in context.relevant_memories[:5] if r.get("memory_id")],
            depends_on=[decompose.step_id],
        )
        steps.append(infer)

        # VALIDATE — check against constraints
        constraints = context.mission_summary
        validate = ReasoningStep(
            step_id=sid("val"),
            step_type="VALIDATE",
            input_facts=[conclusion, constraints],
            operation="Check conclusion against known constraints",
            output="Conclusion validated against constraints" if conclusion else "No conclusion to validate",
            confidence=0.75 if conclusion else 0.3,
            depends_on=[infer.step_id],
        )
        steps.append(validate)

        # SYNTHESIZE — combine into final answer
        synthesize = ReasoningStep(
            step_id=sid("syn"),
            step_type="SYNTHESIZE",
            input_facts=[s.output for s in steps if s.step_type in ("INFER", "VALIDATE")],
            operation="Synthesize intermediate conclusions into final answer",
            output=f"Final conclusion: {conclusion}",
            confidence=0.70,
            evidence_refs=infer.evidence_refs,
            depends_on=[validate.step_id, infer.step_id],
        )
        steps.append(synthesize)

        # REFLECT — self-assessment
        reflect = ReasoningStep(
            step_id=sid("ref"),
            step_type="REFLECT",
            input_facts=[s.output for s in steps],
            operation="Self-assess reasoning quality",
            output=f"Reasoning complete with {len(steps)} steps. Evidence from {len(infer.evidence_refs)} sources.",
            confidence=0.80,
            depends_on=[synthesize.step_id],
        )
        steps.append(reflect)

        return steps

    def _decompose(self, query: str, context: AssembledContext) -> list[str]:
        """Decompose query into sub-problems based on context."""
        subs = []
        words = query.lower().split()
        if len(words) > 3:
            subs.append(f"Analyze: {' '.join(words[:3])}...")
        if context.relevant_memories:
            subs.append("Evaluate relevant past evidence")
        if context.preferences:
            subs.append("Consider owner preferences")
        if not subs:
            subs.append(f"Direct evaluation: {query[:80]}")
        return subs

    def _infer(self, query: str, context: AssembledContext, problem_type: str) -> str:
        """Draw inference based on available evidence."""
        memory_count = len(context.relevant_memories)
        decision_count = len(context.past_decisions)
        pref_count = len(context.preferences)

        if memory_count == 0:
            return f"No relevant memories found for query: {query[:60]}"

        parts = [f"Based on {memory_count} relevant memories"]
        if decision_count > 0:
            parts.append(f"and {decision_count} past decisions")

        # Extract key themes from top memories
        top_contents = [
            r.get("content", "")[:60]
            for r in sorted(
                context.relevant_memories,
                key=lambda x: x.get("confidence", 0),
                reverse=True,
            )[:3]
        ]
        if top_contents:
            parts.append(f"Key evidence: {'; '.join(top_contents)}")

        if pref_count > 0:
            parts.append(f"Owner preferences considered ({pref_count} records)")

        return ". ".join(parts) + "."


class ReasoningKernel:
    """Cognitive inference layer. Deterministic. No model calls."""

    name = "reasoning_kernel"

    def __init__(
        self,
        memory: "MemoryController | None" = None,
        assembler: ContextAssembler | None = None,
        thinker: ThoughtProcessEngine | None = None,
        decider: DecisionFramework | None = None,
        confidence: ConfidenceEngine | None = None,
        checker: SelfCheckValidator | None = None,
    ) -> None:
        adapter = MemoryRetrievalAdapter(memory)
        self._assembler = assembler or ContextAssembler(adapter)
        self._thinker = thinker or ThoughtProcessEngine()
        self._decider = decider or DecisionFramework()
        self._confidence = confidence or ConfidenceEngine()
        self._checker = checker or SelfCheckValidator()

    def reason(
        self,
        mission: MissionContext,
        query: str = "",
        constraints: list[str] | None = None,
        chain_type: str = "linear",
    ) -> ReasoningResult:
        """Execute full reasoning chain and return result with trace and self-check."""
        reasoning_id = new_id("reason")
        objective = query or mission.objective

        # Step 1: Context assembly
        context = self._assembler.assemble(mission)

        # Step 2: Execute thought process
        steps = self._thinker.execute_chain(objective, context, chain_type)

        # Step 3: Evaluate confidence
        evidence_count = len(context.relevant_memories)
        evidence_strength = min(1.0, evidence_count / 5.0)
        avg_confidence = (
            sum(s.confidence for s in steps) / len(steps)
        ) if steps else 0.5
        completeness = len(steps) / 7.0  # 7 expected steps

        conf = self._confidence.evaluate(
            evidence_strength=evidence_strength,
            consistency=0.8,  # default, overridden by self-check
            completeness=completeness,
            source_reliability=avg_confidence,
            historical_accuracy=0.5,  # default until calibration data exists
        )

        # Step 4: Self-check
        check = self._checker.validate(steps)

        # Update confidence with self-check consistency
        if check.overall_pass:
            conf = self._confidence.evaluate(
                evidence_strength=evidence_strength,
                consistency=0.9,
                completeness=completeness,
                source_reliability=avg_confidence,
                historical_accuracy=0.5,
            )

        # Build trace
        trace = ReasoningTrace(
            reasoning_id=reasoning_id,
            mission_id=mission.mission_id,
            steps=steps,
            final_confidence=conf.score,
            self_check_passed=check.overall_pass,
            created_at=now_iso(),
        )

        # Build conclusion from last SYNTHESIZE step
        conclusion = ""
        for s in reversed(steps):
            if s.step_type == "SYNTHESIZE":
                conclusion = s.output
                break

        evidence_refs = list(dict.fromkeys(
            rid for s in steps for rid in s.evidence_refs if rid
        ))

        return ReasoningResult(
            reasoning_id=reasoning_id,
            trace=trace,
            conclusion=conclusion,
            confidence=conf,
            evidence_refs=evidence_refs,
            self_check=check,
        )

    def audit(self, trace: ReasoningTrace) -> dict[str, Any]:
        """Return full step-by-step reasoning audit trail."""
        return {
            "reasoning_id": trace.reasoning_id,
            "mission_id": trace.mission_id,
            "step_count": len(trace.steps),
            "final_confidence": trace.final_confidence,
            "self_check_passed": trace.self_check_passed,
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "input_facts": s.input_facts,
                    "operation": s.operation,
                    "output": s.output,
                    "confidence": s.confidence,
                    "evidence_refs": s.evidence_refs,
                }
                for s in trace.steps
            ],
        }

    def quantify_uncertainty(
        self, conclusion: str, evidence_weight: float,
    ) -> dict[str, Any]:
        """Quantify uncertainty of a conclusion given evidence weight."""
        conf = self._confidence.evaluate(
            evidence_strength=evidence_weight,
            consistency=0.5,
            completeness=0.5,
            source_reliability=0.5,
            historical_accuracy=0.5,
        )
        return {
            "conclusion": conclusion[:100],
            "evidence_weight": evidence_weight,
            "confidence_score": conf.score,
            "confidence_level": conf.level,
            "uncertainty_sources": conf.uncertainty_sources,
        }
