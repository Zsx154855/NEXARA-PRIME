"""NEXARA Sovereign Council V2 — Multi-Agent Autonomous Council System

The NEXARA Sovereign Council transforms independent AI models (ChatGPT, Codex,
Claude, Hermes, Grok, DeepSeek) from isolated chat windows into a coordinated
agent organization governed by NSEC V2.1.

Architecture:
    Council (9 seats)
    ├── H-CHAIRMAN  — Final decision, objective convergence
    ├── H-STAFF     — Context compression, task dispatch, minutes
    ├── H-ARCH      — Architecture design, system boundaries
    ├── H-CODE      — Implementation, testing, refactoring
    ├── H-EXEC      — Hermes execution orchestration
    ├── H-RED       — Red team attack, risk discovery (VETO)
    ├── H-JUDGE     — Final adjudication (VETO)
    ├── H-MEM       — Memory, Knowledge OS, Decision Ledger
    └── H-TOKEN     — Token budget, context optimization

Pipeline:
    Requirement → DNA → Deliberation → Red Team → Judge → Plan →
    Hermes Runner → Evidence → Verification → Memory Commit

Key Modules:
    - MissionDNA: Structured mission specification (mission_dna.py)
    - ExecutionPipeline: 10-stage governed pipeline (pipeline.py)
    - MissionRouter: Agent assignment by mission type/risk (runtime/mission_router.py)
    - ConflictResolver: Vote tie-breaking, veto handling (runtime/conflict_resolver.py)
    - TokenGovernor: Budget management, optimization (runtime/token_governor.py)

Integration:
    - NexaraRuntime: Pipeline stages map to runtime execution
    - NSEC V2.1: All decisions governed by sovereign engineering constitution
    - Hermes Agent: Multi-agent spawning via delegate_task and tmux
    - Memory System: Persistent cross-session council knowledge
    - Evidence System: Immutable mission evidence with SHA256 integrity

Configuration:
    - constitution/CONSTITUTION_V2.md — Council constitution
    - constitution/council_rules.yaml — Rules of procedure
    - agents/*.yaml — Agent role definitions (9 seats)
    - governance/approval_policy.yaml — Approval levels L0-L4
    - governance/risk_policy.yaml — Risk classification R0-R4

Usage:
    from nexara_prime.council import (
        MissionDNA, DNABuilder, MissionRisk, DNAStatus,
        ExecutionPipeline, PipelineState, PipelineStage, StageStatus,
        MissionRouter, AgentSeat, RoutingDecision,
        ConflictResolver, Conflict, ConflictType,
        TokenGovernor, TokenBudget, TokenMode, TokenUsage,
        create_council_mission, run_council_pipeline,
    )

    # Quick start
    dna = create_council_mission(
        objective="Fix bug in authentication module",
        risk=MissionRisk.R2_MODERATE,
    )
    result = run_council_pipeline(dna)
    print(result["receipt"]["test_results"])
"""

from nexara_prime.council.mission_dna import (
    DNABuilder,
    DNAStatus,
    MissionDNA,
    MissionRisk,
)
from nexara_prime.council.pipeline import (
    ExecutionPipeline,
    PipelineStage,
    PipelineState,
    StageResult,
    StageStatus,
)
from nexara_prime.council.runtime.mission_router import (
    AgentSeat,
    MissionRouter,
    RoutingDecision,
    RoutingStrategy,
    route_mission,
)
from nexara_prime.council.runtime.conflict_resolver import (
    Conflict,
    ConflictResolver,
    ConflictType,
    ResolutionType,
    resolve,
)
from nexara_prime.council.runtime.token_governor import (
    TokenBudget,
    TokenGovernor,
    TokenMode,
    TokenUsage,
)

__all__ = [
    # DNA
    "MissionDNA", "DNABuilder", "MissionRisk", "DNAStatus",
    # Pipeline
    "ExecutionPipeline", "PipelineState", "PipelineStage", "StageStatus", "StageResult",
    # Router
    "MissionRouter", "AgentSeat", "RoutingDecision", "RoutingStrategy", "route_mission",
    # Conflict
    "ConflictResolver", "Conflict", "ConflictType", "ResolutionType", "resolve",
    # Token
    "TokenGovernor", "TokenBudget", "TokenMode", "TokenUsage",
    # Convenience
    "create_council_mission", "run_council_pipeline",
]


def create_council_mission(
    objective: str,
    risk: MissionRisk = MissionRisk.R1_LOW,
    constraints: list[str] | None = None,
    agents: list[str] | None = None,
    tools: list[str] | None = None,
    permissions: list[str] | None = None,
    expected_output: str | None = None,
    verification: list[str] | None = None,
    rollback: list[str] | None = None,
) -> MissionDNA:
    """Create a council mission with sensible defaults.

    This is the quick-start entry point for council missions.
    Defaults are applied for all optional fields.

    Args:
        objective: What this mission must accomplish.
        risk: Risk classification (default R1_LOW).
        constraints: Hard constraints (auto-populated if None).
        agents: Council agents (auto-populated based on risk if None).
        tools: Authorized tools (auto-populated if None).
        permissions: Explicit permissions (auto-populated if None).
        expected_output: Expected output description (auto-generated if None).
        verification: Verification steps (auto-populated if None).
        rollback: Rollback steps (auto-populated if None).

    Returns:
        Complete MissionDNA ready for pipeline execution.
    """
    # Auto-populate agents based on risk
    if agents is None:
        agents = _default_agents(risk)

    # Auto-populate tools
    if tools is None:
        tools = [
            "terminal", "file", "search_files", "read_file", "write_file",
            "patch", "web_search", "delegate_task", "memory",
        ]

    # Auto-populate permissions
    if permissions is None:
        permissions = ["read", "write_local", "execute_local"]
        if risk >= MissionRisk.R3_HIGH:
            permissions = ["read"]  # Restrict high-risk missions

    # Auto-populate constraints
    if constraints is None:
        constraints = [
            "NSEC V2.1 compliance",
            "No production database modification",
            "No force push or merge without approval",
            "Evidence required for all state changes",
        ]
        if risk >= MissionRisk.R3_HIGH:
            constraints.append("Human approval required before execution")

    # Auto-generate expected output
    if expected_output is None:
        expected_output = (
            f"Complete '{objective}' with verifiable evidence, "
            f"test results, and a BUILD_RECEIPT. Risk level: {risk.value}."
        )

    # Auto-populate verification
    if verification is None:
        verification = [
            "All pipeline stages completed without BLOCKED",
            "Evidence package generated with SHA256 hashes",
            "BUILD_RECEIPT contains all required fields",
            "No NSEC violations detected",
            "Red team risk assessment passed or waived",
        ]

    # Auto-populate rollback
    if rollback is None:
        rollback = [
            "Restore git state to pre-mission commit",
            "Remove any created evidence files if mission rejected",
            "Notify H-CHAIRMAN of rollback completion",
            "Record rollback in Decision Ledger",
        ]

    builder = (
        DNABuilder()
        .with_objective(objective)
        .with_constraints(*constraints)
        .with_agents(*agents)
        .with_tools(*tools)
        .with_permissions(*permissions)
        .with_expected_output(expected_output)
        .with_verification(*verification)
        .with_rollback(*rollback)
        .with_risk(risk)
    )

    # Determine approval level from risk
    risk_to_approval = {
        MissionRisk.R0_NEGLIGIBLE: "L0_ROUTINE",
        MissionRisk.R1_LOW: "L1_STANDARD",
        MissionRisk.R2_MODERATE: "L2_SIGNIFICANT",
        MissionRisk.R3_HIGH: "L3_CRITICAL",
        MissionRisk.R4_CRITICAL: "L4_CONSTITUTIONAL",
    }
    builder.with_approval_level(risk_to_approval.get(risk, "L1_STANDARD"))

    return builder.build()


def run_council_pipeline(dna: MissionDNA) -> dict:
    """Run the full council pipeline on a mission DNA.

    Args:
        dna: Complete MissionDNA to execute.

    Returns:
        Dict with 'state' (PipelineState) and 'receipt' (dict).
    """
    pipeline = ExecutionPipeline(dna)
    state = pipeline.run()
    receipt = pipeline.generate_receipt(state)
    return {"state": state, "receipt": receipt}


def _default_agents(risk: MissionRisk) -> list[str]:
    """Determine default agent assignment based on risk level."""
    base = ["H-CHAIRMAN", "H-STAFF", "H-CODE"]

    if risk >= MissionRisk.R2_MODERATE:
        base.extend(["H-ARCH", "H-MEM"])
    if risk >= MissionRisk.R3_HIGH:
        base.extend(["H-RED", "H-JUDGE"])
    if risk >= MissionRisk.R4_CRITICAL:
        base = ["H-CHAIRMAN", "H-STAFF", "H-ARCH", "H-CODE", "H-EXEC",
                "H-RED", "H-JUDGE", "H-MEM", "H-TOKEN"]

    # Always include TOKEN for budget tracking
    if "H-TOKEN" not in base:
        base.append("H-TOKEN")

    return base
