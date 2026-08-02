"""Mission Intelligence Engine — Phase 4A entry point for mission compilation.

Deterministic 5-stage pipeline: parse→classify→decompose→assess→compile.
Brain Above Runtime — reads MemoryController, produces MissionContract.
Zero model calls, zero network, zero file I/O, zero side effects.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, TYPE_CHECKING

from nexara_prime.brain.mission_types import (
    ClassificationResult,
    DecompositionResult,
    DependencyEdge,
    IntentResult,
    MissionContract,
    RiskAssessment,
    TaskNode,
)
from nexara_prime.models import now_iso, new_id

if TYPE_CHECKING:
    from nexara_prime.brain.memory_controller import MemoryController


class IntentParseError(ValueError):
    """Raised when user goal cannot be parsed."""


class ContractCompileError(ValueError):
    """Raised when contract compilation fails due to missing required inputs."""


class MissionIntelligenceEngine:
    """Deterministic mission intelligence pipeline.

    State machine: IDLE → PARSING → CLASSIFYING → DECOMPOSING → ASSESSING → COMPILING → DONE

    Rules:
      - NO self-transitions — always advance forward.
      - NO state regression — cannot return except via re-instantiation.
      - NO skip — all 5 processing states must execute.
      - IDEMPOTENCY — every method has sha256-based idempotency key.
      - FAIL-SAFE — defaults to R2, approval_required=True.

    Architecture:
      - MemoryController: read-only (recall, rank_retrieve, cross_layer_query).
      - NEVER calls commit(), NEVER writes memory.
      - NEVER calls models, NEVER opens network.
      - Brain Above Runtime — produces contract for kernel submission.
    """

    def __init__(self, memory_controller: MemoryController | None = None) -> None:
        self._mc = memory_controller
        self._cache: dict[str, Any] = {}
        self._state: str = "IDLE"

    @property
    def state(self) -> str:
        return self._state

    # ── Step 1: parse_intent ─────────────────────────────────────────────────

    def parse_intent(self, user_goal: str, context: dict[str, Any] | None = None) -> IntentResult:
        """Parse raw user input into structured intent.

        Idempotency: sha256(user_goal + sorted(context.keys())).
        Risk: R0 — deterministic parse, no external calls.

        Args:
            user_goal: Raw user input string.
            context: Optional session context.

        Returns:
            IntentResult with goal_type, entities, priority, domain.
        """
        key = self._idempotency_key("parse", user_goal, context)
        if key in self._cache:
            self._state = "PARSING"
            return self._cache[key]

        ctx = context or {}

        if not user_goal or not user_goal.strip():
            raise IntentParseError("user_goal is empty")

        goal = user_goal.strip()
        tokens = goal.split()

        # Classify goal type by keyword signals
        goal_lower = goal.lower()
        if any(kw in goal_lower for kw in ("fix", "repair", "recover", "rescue", "restore")):
            gtype = "RECOVERY"
        elif any(kw in goal_lower for kw in ("deploy", "release", "publish", "ship")):
            gtype = "DEPLOY"
        elif any(kw in goal_lower for kw in ("audit", "inspect", "review code", "scan", "check for")):
            gtype = "AUDIT"
        elif any(kw in goal_lower for kw in ("research", "investigate", "explore", "study", "find out")):
            gtype = "RESEARCH"
        elif any(kw in goal_lower for kw in ("refactor", "rewrite", "restructure", "redesign", "reorganize")):
            gtype = "REFACTOR"
        elif any(kw in goal_lower for kw in ("write", "create", "build", "implement", "add", "generate", "code", "make")):
            gtype = "CODE_GEN"
        else:
            gtype = "UNKNOWN"

        # Extract entities: filenames, module names, keywords
        entities = []
        for token in tokens:
            clean = token.strip(".,;:!?\"'()[]{}")
            if "." in clean or "_" in clean or clean.endswith(".py"):
                entities.append(clean)
            elif len(clean) > 3 and clean[0].isupper():
                entities.append(clean)

        # Determine priority from signals
        priority = ctx.get("priority", "medium")
        if any(kw in goal_lower for kw in ("urgent", "critical", "asap", "emergency")):
            priority = "critical"
        elif any(kw in goal_lower for kw in ("important", "high priority")):
            priority = "high"

        # Infer domain
        domain = self._infer_domain(goal_lower, entities)

        result = IntentResult(
            goal_type=gtype,
            entities=entities,
            priority=priority,
            domain=domain,
            raw_tokens=tokens,
        )
        self._cache[key] = result
        self._state = "PARSING"
        return result

    # ── Step 2: classify_mission ─────────────────────────────────────────────

    def classify_mission(
        self,
        intent: IntentResult,
        history: list[dict[str, Any]] | None = None,
    ) -> ClassificationResult:
        """Classify mission type with confidence scoring.

        Idempotency: sha256(intent.goal_type + intent.domain).
        Risk: R0 — classification only, no execution.

        Args:
            intent: Parsed intent result.
            history: Optional historical mission records for confidence boost.

        Returns:
            ClassificationResult with mission_type, confidence, evidence_refs.
        """
        key = self._idempotency_key("classify", intent.goal_type, {"domain": intent.domain})
        if key in self._cache:
            self._state = "CLASSIFYING"
            return self._cache[key]

        mission_type = intent.goal_type
        confidence = 0.5
        fallback = ""
        evidence_refs: list[str] = []

        # Boost confidence based on signals
        if len(intent.entities) >= 2:
            confidence += 0.1
        if intent.priority in ("high", "critical"):
            confidence += 0.05
        if intent.domain != "unknown":
            confidence += 0.1

        # Query history for similar missions
        if history and len(history) > 0:
            matches = [h for h in history if h.get("type") == mission_type]
            if matches:
                confidence += 0.15
                evidence_refs = [h.get("evidence_id", "") for h in matches[:3] if h.get("evidence_id")]

        # Query MemoryController for historical patterns
        if self._mc is not None and mission_type != "UNKNOWN":
            try:
                similar = self._mc.recall(mission_id=None, layer="semantic")
                related = [r for r in similar if mission_type.lower() in json.dumps(r).lower()]
                if related:
                    confidence += 0.05
                    evidence_refs.extend(
                        r.get("evidence_id", "") for r in related[:2] if r.get("evidence_id")
                    )
            except Exception:
                pass

        if mission_type == "UNKNOWN":
            fallback = "insufficient_signals"
            confidence = 0.0

        confidence = min(confidence, 1.0)
        result = ClassificationResult(
            mission_type=mission_type,
            confidence=round(confidence, 2),
            fallback=fallback,
            evidence_refs=evidence_refs[:5],
        )
        self._cache[key] = result
        self._state = "CLASSIFYING"
        return result

    # ── Step 3: decompose_goal ───────────────────────────────────────────────

    def decompose_goal(
        self,
        objective: str,
        mission_type: str,
        constraints: dict[str, Any] | None = None,
    ) -> DecompositionResult:
        """Break objective into ordered task sequence with dependencies.

        Idempotency: sha256(objective + mission_type).
        Risk: R1 — reads memory, produces plan; no writes.

        Args:
            objective: Mission objective string.
            mission_type: Classified mission type.
            constraints: Optional constraint dict.

        Returns:
            DecompositionResult with tasks, dependencies, parallel groups.
        """
        key = self._idempotency_key("decompose", objective, {"type": mission_type})
        if key in self._cache:
            self._state = "DECOMPOSING"
            return self._cache[key]

        cons = constraints or {}
        tasks: list[TaskNode] = []
        deps: list[DependencyEdge] = []
        order = 0

        # Generate tasks based on mission type
        if mission_type == "CODE_GEN":
            order += 1; tasks.append(TaskNode(f"t{order}", "Analyze requirements", "low", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Design solution approach", "medium", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Implement core logic", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Write tests", "medium", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Verify and document", "low", [f"t{order-1}"], order))
        elif mission_type == "REFACTOR":
            order += 1; tasks.append(TaskNode(f"t{order}", "Audit current codebase", "medium", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Identify refactor targets", "low", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Apply refactoring", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Run regression tests", "medium", [f"t{order-1}"], order))
        elif mission_type == "RESEARCH":
            order += 1; tasks.append(TaskNode(f"t{order}", "Define research scope", "low", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Gather information", "medium", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Analyze findings", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Produce report", "medium", [f"t{order-1}"], order))
        elif mission_type == "AUDIT":
            order += 1; tasks.append(TaskNode(f"t{order}", "Define audit criteria", "low", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Scan target system", "medium", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Compile findings", "medium", [f"t{order-1}"], order))
        elif mission_type == "DEPLOY":
            order += 1; tasks.append(TaskNode(f"t{order}", "Verify pre-deploy checklist", "medium", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Stage deployment", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Deploy", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Verify post-deploy", "medium", [f"t{order-1}"], order))
        elif mission_type == "RECOVERY":
            order += 1; tasks.append(TaskNode(f"t{order}", "Diagnose failure", "high", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Apply fix", "high", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Verify recovery", "medium", [f"t{order-1}"], order))
        else:  # UNKNOWN
            order += 1; tasks.append(TaskNode(f"t{order}", "Clarify objective", "medium", [], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Execute task", "medium", [f"t{order-1}"], order))
            order += 1; tasks.append(TaskNode(f"t{order}", "Verify result", "low", [f"t{order-1}"], order))

        # Build dependency edges from task dependency lists
        for t in tasks:
            for dep_id in t.dependencies:
                deps.append(DependencyEdge(from_task=dep_id, to_task=t.task_id, type="sequential"))

        # Identify parallel groups (tasks with no mutual dependencies)
        parallel_groups: list[list[str]] = []
        remaining = [t.task_id for t in tasks]
        while remaining:
            group = [tid for tid in remaining if not any(
                e.to_task == tid and e.from_task in remaining
                for e in deps
            )]
            if group:
                parallel_groups.append(group)
                remaining = [tid for tid in remaining if tid not in group]
            else:
                break

        # Adjust by constraints
        if cons.get("time_limit"):
            effort_map = {"low": "medium", "medium": "high", "high": "high"}
            for t in tasks:
                t = TaskNode(t.task_id, t.description, effort_map.get(t.estimated_effort, t.estimated_effort), t.dependencies, t.order)

        # Query MemoryController for decomposition patterns
        source = "generated"
        if self._mc is not None:
            try:
                similar = self._mc.rank_retrieve(query=f"decomposition:{mission_type}", top_k=5)
                if similar:
                    source = "pattern_matched"
            except Exception:
                pass

        result = DecompositionResult(
            tasks=tasks,
            dependencies=deps,
            estimated_effort=self._effort_label(len(tasks)),
            parallel_groups=parallel_groups,
            source=source,
        )
        self._cache[key] = result
        self._state = "DECOMPOSING"
        return result

    # ── Step 4: assess_risk ──────────────────────────────────────────────────

    def assess_risk(
        self,
        mission_type: str,
        tasks: list[TaskNode],
        constraints: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Assess mission risk using R0-R4 scale.

        Idempotency: sha256(mission_type + str(len(tasks)) + sorted constraints).
        Risk: R1 — reads memory, computes risk; no writes.

        Classification factors:
          - mission_type risk profile
          - task count
          - constraint sensitivity
          - historical failure rate from MemoryController

        Args:
            mission_type: Classified mission type.
            tasks: Decomposed task list.
            constraints: Optional constraint dict.

        Returns:
            RiskAssessment with risk_level, score, factors, mitigations.
        """
        cons = constraints or {}
        key = self._idempotency_key("risk", mission_type, {
            "task_count": len(tasks),
            "constraints": sorted(cons.keys()),
        })
        if key in self._cache:
            self._state = "ASSESSING"
            return self._cache[key]

        # Base risk by mission type
        risk_map: dict[str, tuple[str, float]] = {
            "CODE_GEN": ("R1", 0.20),
            "RESEARCH": ("R1", 0.15),
            "REFACTOR": ("R2", 0.40),
            "DEPLOY": ("R3", 0.70),
            "AUDIT": ("R1", 0.15),
            "RECOVERY": ("R2", 0.45),
            "UNKNOWN": ("R2", 0.50),
        }

        base_risk, base_score = risk_map.get(mission_type, ("R2", 0.50))
        risk_score = base_score
        risk_factors: list[str] = [f"mission_type={mission_type}"]
        mitigations: list[str] = []

        # Adjust by task count
        n = len(tasks)
        if n <= 3:
            risk_score -= 0.05
        elif n <= 10:
            pass
        elif n <= 20:
            risk_score += 0.10
            risk_factors.append(f"complex_task_count={n}")
        else:
            risk_score += 0.20
            risk_factors.append(f"very_complex_task_count={n}")

        # Adjust by constraints
        if cons.get("time_limit"):
            risk_score += 0.05
            risk_factors.append("has_time_constraint")
        if cons.get("budget_limit"):
            risk_score += 0.03
        if cons.get("forbidden_actions"):
            risk_score += 0.10
            risk_factors.append("has_forbidden_actions")
        if cons.get("security_constraint"):
            risk_score += 0.10
            risk_factors.append("has_security_constraint")

        # Query historical failure rate
        if self._mc is not None:
            try:
                failures = self._mc.recall(mission_id=None, layer="episodic")
                related = [f for f in failures if mission_type.lower() in json.dumps(f).lower()]
                if related:
                    fail_rate = sum(1 for f in related if "failure" in str(f.get("kind", ""))) / max(len(related), 1)
                    if fail_rate > 0.3:
                        risk_score += 0.20
                        risk_factors.append(f"high_historical_failure_rate={fail_rate:.0%}")
                    elif fail_rate > 0.1:
                        risk_score += 0.10
                    elif fail_rate < 0.05:
                        risk_score -= 0.05
            except Exception:
                risk_score += 0.05
                risk_factors.append("unknown_territory")

        risk_score = max(0.0, min(1.0, risk_score))

        # Map score to R0-R4 using half-open intervals, rounding UP
        if risk_score < 0.15:
            risk_level = "R0"
        elif risk_score < 0.35:
            risk_level = "R1"
        elif risk_score < 0.65:
            risk_level = "R2"
        elif risk_score < 0.85:
            risk_level = "R3"
        else:
            risk_level = "R4"

        approval_required = risk_level in ("R2", "R3", "R4")

        # Generate mitigations
        if risk_level in ("R2", "R3", "R4"):
            mitigations.append("user_confirmation_required")
        if risk_level in ("R3", "R4"):
            mitigations.append("human_approval_required")
            mitigations.append("rollback_snapshot_required")
        if risk_level == "R4":
            mitigations.append("dual_verification_required")
            mitigations.append("limited_blast_radius")
        if risk_level in ("R0", "R1"):
            mitigations.append("evidence_recording")

        result = RiskAssessment(
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            risk_factors=risk_factors,
            mitigations=mitigations,
            approval_required=approval_required,
            source="computed",
        )
        self._cache[key] = result
        self._state = "ASSESSING"
        return result

    # ── Step 5: compile_contract ─────────────────────────────────────────────

    def compile_contract(
        self,
        mission_id: str,
        intent: IntentResult,
        classification: ClassificationResult,
        decomposition: DecompositionResult,
        risk: RiskAssessment,
    ) -> MissionContract:
        """Compile all analysis into a governed MissionContract.

        Idempotency: sha256(mission_id).
        Risk: R1 — compilation only; no execution, no memory write.

        Args:
            mission_id: Unique mission identifier.
            intent: Parsed intent result.
            classification: Classification result.
            decomposition: Decomposition result.
            risk: Risk assessment result.

        Returns:
            MissionContract ready for kernel submission.

        Raises:
            ContractCompileError: If mission_id or risk is None.
        """
        if not mission_id:
            raise ContractCompileError("mission_id is required")
        if risk is None:
            raise ContractCompileError("risk assessment is required")

        key = self._idempotency_key("compile", mission_id)
        if key in self._cache:
            self._state = "COMPILING"
            return self._cache[key]

        # Build objective from intent + classification
        raw_tokens = intent.raw_tokens
        objective = " ".join(raw_tokens) if raw_tokens else f"{classification.mission_type}: user goal"

        # Derive success criteria from tasks
        success_criteria = [
            f"Complete: {t.description}" for t in decomposition.tasks
        ]

        # Map capabilities from mission_type + tasks
        cap_map: dict[str, list[str]] = {
            "CODE_GEN": ["coding", "testing"],
            "RESEARCH": ["reasoning", "web_search"],
            "REFACTOR": ["coding", "architecture", "testing"],
            "DEPLOY": ["deployment", "testing"],
            "AUDIT": ["reasoning", "inspection"],
            "RECOVERY": ["diagnosis", "coding"],
            "UNKNOWN": ["reasoning"],
        }
        required_capabilities = cap_map.get(classification.mission_type, ["reasoning"])

        compiled_at = now_iso()

        # Compute contract SHA256 (excludes timestamp for determinism)
        payload = {
            "mission_id": mission_id,
            "objective": objective,
            "risk_level": risk.risk_level,
            "approval_required": risk.approval_required,
            "task_count": len(decomposition.tasks),
        }
        contract_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]

        result = MissionContract(
            mission_id=mission_id,
            objective=objective,
            success_criteria=success_criteria,
            required_capabilities=required_capabilities,
            risk_level=risk.risk_level,
            approval_required=risk.approval_required,
            contract_sha256=contract_sha256,
            compiled_at=compiled_at,
        )
        self._cache[key] = result
        self._state = "COMPILING"
        return result

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def run_pipeline(
        self,
        user_goal: str,
        *,
        context: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        mission_id: str | None = None,
    ) -> MissionContract:
        """Run the full 5-stage pipeline in one call.

        Returns the compiled MissionContract ready for kernel submission.
        """
        if mission_id is None:
            mission_id = new_id("mis")
        ctx = context or {}
        cons = constraints or {}

        intent = self.parse_intent(user_goal, ctx)
        classification = self.classify_mission(intent)
        decomposition = self.decompose_goal(
            " ".join(intent.raw_tokens), classification.mission_type, cons,
        )
        risk = self.assess_risk(classification.mission_type, decomposition.tasks, cons)
        contract = self.compile_contract(mission_id, intent, classification, decomposition, risk)
        self._state = "DONE"
        return contract

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _idempotency_key(stage: str, *inputs: Any, **kwinputs: Any) -> str:
        """Compute deterministic sha256 idempotency key."""
        raw = stage + "|" + json.dumps(list(inputs) + sorted(kwinputs.items()), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _infer_domain(goal_lower: str, entities: list[str]) -> str:
        """Infer domain from goal text and entity signals."""
        domain_signals = {
            "authentication": ("auth", "login", "oauth", "jwt", "session"),
            "database": ("db", "sql", "mongo", "postgres", "query"),
            "api": ("api", "endpoint", "rest", "graphql", "route"),
            "ci/cd": ("ci", "cd", "pipeline", "deploy", "github actions"),
            "testing": ("test", "pytest", "coverage", "mock"),
            "frontend": ("ui", "react", "css", "component", "page"),
            "infrastructure": ("docker", "k8s", "aws", "server", "cloud"),
            "security": ("security", "vuln", "exploit", "cve"),
        }
        for domain, signals in domain_signals.items():
            if any(s in goal_lower for s in signals):
                return domain
        if entities:
            return "codebase"
        return "general"

    @staticmethod
    def _effort_label(task_count: int) -> str:
        if task_count <= 3:
            return "low"
        elif task_count <= 7:
            return "medium"
        return "high"
