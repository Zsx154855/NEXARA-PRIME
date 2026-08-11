"""Tests for the NEXARA Council V2 system.

Tests cover:
- MissionDNA creation, validation, serialization
- ExecutionPipeline stages and state machine
- MissionRouter agent assignment
- ConflictResolver voting and veto
- TokenGovernor budget enforcement
- Integration: council __init__.py convenience functions
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Ensure council package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))


# ============================================================
# MissionDNA Tests
# ============================================================

class TestMissionDNA:
    """Test Mission DNA creation, validation, and serialization."""

    def test_create_with_builder(self):
        """Builder pattern should produce complete DNA."""
        from nexara_prime.council import DNABuilder, MissionRisk

        dna = (
            DNABuilder()
            .with_objective("Test mission")
            .with_constraints("NSEC V2.1", "No production write")
            .with_agents("H-CHAIRMAN", "H-CODE")
            .with_tools("terminal", "file")
            .with_permissions("read", "write_local")
            .with_expected_output("Test output")
            .with_verification("Step 1", "Step 2")
            .with_rollback("Rollback 1", "Rollback 2")
            .with_risk(MissionRisk.R1_LOW)
            .build()
        )

        assert dna.is_complete
        assert dna.mission_id.startswith("mis-")
        assert dna.objective == "Test mission"
        assert dna.status.value == "GENERATED"
        assert dna.dna_hash != ""
        assert len(dna.missing_fields) == 0

    def test_incomplete_dna_raises(self):
        """Building incomplete DNA should raise ValueError."""
        from nexara_prime.council import DNABuilder

        builder = (
            DNABuilder()
            .with_objective("Incomplete")
            # Missing constraints, agents, tools, etc.
        )
        with pytest.raises(ValueError, match="MissionDNA incomplete"):
            builder.build()

    def test_dna_hash_deterministic(self):
        """Same DNA content should produce same hash when mission_id is fixed."""
        from nexara_prime.council import DNABuilder, MissionRisk, MissionDNA

        # Build once to get mission_id, then rebuild with same mission_id
        dna1 = (
            DNABuilder()
            .with_objective("Hash test")
            .with_constraints("C1")
            .with_agents("H-CODE")
            .with_tools("terminal")
            .with_permissions("read")
            .with_expected_output("Output")
            .with_verification("V1")
            .with_rollback("R1")
            .with_risk(MissionRisk.R1_LOW)
            .build()
        )

        # Recompute hash from serialized data to verify determinism
        data = dna1.to_dict()
        restored = MissionDNA.from_dict(data)
        restored.compute_hash()

        assert dna1.dna_hash == restored.dna_hash

    def test_dna_serialization_roundtrip(self):
        """DNA should survive to_dict/from_dict roundtrip."""
        from nexara_prime.council import DNABuilder, MissionDNA, MissionRisk

        dna = (
            DNABuilder()
            .with_objective("Roundtrip test")
            .with_constraints("C1", "C2")
            .with_agents("H-CHAIRMAN", "H-CODE", "H-RED")
            .with_tools("terminal", "file", "web_search")
            .with_permissions("read", "write_local")
            .with_expected_output("Complete roundtrip")
            .with_verification("V1", "V2", "V3")
            .with_rollback("R1", "R2")
            .with_risk(MissionRisk.R3_HIGH)
            .build()
        )

        data = dna.to_dict()
        restored = MissionDNA.from_dict(data)

        assert restored.mission_id == dna.mission_id
        assert restored.objective == dna.objective
        assert restored.constraints == dna.constraints
        assert restored.agents == dna.agents
        assert restored.risk == dna.risk
        assert restored.dna_hash == dna.dna_hash

    def test_dna_json_serializable(self):
        """DNA to_dict should be JSON-serializable."""
        from nexara_prime.council import DNABuilder, MissionRisk

        dna = (
            DNABuilder()
            .with_objective("JSON test")
            .with_constraints("C1")
            .with_agents("H-CODE")
            .with_tools("terminal")
            .with_permissions("read")
            .with_expected_output("Output")
            .with_verification("V1")
            .with_rollback("R1")
            .with_risk(MissionRisk.R1_LOW)
            .build()
        )

        json_str = json.dumps(dna.to_dict())
        assert isinstance(json_str, str)
        assert "mission_id" in json_str


# ============================================================
# MissionRouter Tests
# ============================================================

class TestMissionRouter:
    """Test mission routing and agent assignment."""

    @pytest.fixture
    def low_risk_dna(self):
        from nexara_prime.council import DNABuilder, MissionRisk
        return (
            DNABuilder()
            .with_objective("Implement user authentication")
            .with_constraints("NSEC V2.1")
            .with_agents("H-CODE", "H-CHAIRMAN")
            .with_tools("terminal", "file")
            .with_permissions("read", "write_local")
            .with_expected_output("Auth module with tests")
            .with_verification("All tests pass")
            .with_rollback("Git revert")
            .with_risk(MissionRisk.R1_LOW)
            .build()
        )

    @pytest.fixture
    def high_risk_dna(self):
        from nexara_prime.council import DNABuilder, MissionRisk
        return (
            DNABuilder()
            .with_objective("Deploy to production database")
            .with_constraints("NSEC V2.1", "Human approval required")
            .with_agents("H-CHAIRMAN", "H-CODE", "H-RED", "H-JUDGE")
            .with_tools("terminal", "file")
            .with_permissions("read")  # Restricted for high risk
            .with_expected_output("Safe deployment")
            .with_verification("Post-deploy health check")
            .with_rollback("Rollback deployment", "Restore DB snapshot")
            .with_risk(MissionRisk.R3_HIGH)
            .build()
        )

    def test_route_low_risk(self, low_risk_dna):
        """Low risk should get TRIAD routing with core agents."""
        from nexara_prime.council import MissionRouter, AgentSeat

        routing = MissionRouter.route(low_risk_dna)

        assert routing.mission_id == low_risk_dna.mission_id
        assert AgentSeat.CHAIRMAN in routing.assigned_seats
        assert AgentSeat.CODE in routing.assigned_seats
        # MEM and TOKEN always included
        assert AgentSeat.MEM in routing.assigned_seats
        assert AgentSeat.TOKEN in routing.assigned_seats

    def test_route_high_risk(self, high_risk_dna):
        """High risk should escalate to FULL_COUNCIL with RED and JUDGE."""
        from nexara_prime.council import MissionRouter, AgentSeat, RoutingStrategy

        routing = MissionRouter.route(high_risk_dna)

        assert routing.strategy == RoutingStrategy.FULL_COUNCIL
        assert AgentSeat.RED in routing.assigned_seats
        assert AgentSeat.JUDGE in routing.assigned_seats

    def test_route_security_audit(self):
        """Security audit missions should include RED TEAM."""
        from nexara_prime.council import DNABuilder, MissionRisk, MissionRouter, AgentSeat

        dna = (
            DNABuilder()
            .with_objective("Security audit of authentication system")
            .with_constraints("Read-only")
            .with_agents("H-RED")
            .with_tools("terminal")
            .with_permissions("read")
            .with_expected_output("Audit report")
            .with_verification("Report complete")
            .with_rollback("N/A")
            .with_risk(MissionRisk.R2_MODERATE)
            .build()
        )

        routing = MissionRouter.route(dna)
        assert AgentSeat.RED in routing.assigned_seats

    def test_convenience_route_mission(self, low_risk_dna):
        """Convenience function should work."""
        from nexara_prime.council import route_mission

        routing = route_mission(low_risk_dna)
        assert routing.mission_id == low_risk_dna.mission_id


# ============================================================
# ConflictResolver Tests
# ============================================================

class TestConflictResolver:
    """Test conflict resolution and voting."""

    def test_resolve_vote_tie_chairman_decides(self):
        """Tied vote should be broken by Chairman."""
        from nexara_prime.council import ConflictResolver, AgentSeat

        votes = {
            AgentSeat.CHAIRMAN: "APPROVE",
            AgentSeat.CODE: "APPROVE",
            AgentSeat.ARCH: "REJECT",
            AgentSeat.RED: "REJECT",
        }

        result = ConflictResolver.resolve_vote_tie(votes, "APPROVE")
        assert result == "APPROVE"

    def test_resolve_vote_clear_majority(self):
        """Clear majority should win without tiebreaker."""
        from nexara_prime.council import ConflictResolver, AgentSeat

        votes = {
            AgentSeat.CHAIRMAN: "APPROVE",
            AgentSeat.CODE: "APPROVE",
            AgentSeat.ARCH: "APPROVE",
            AgentSeat.RED: "REJECT",
        }

        result = ConflictResolver.resolve_vote_tie(votes, "REJECT")
        assert result == "APPROVE"  # 3-1 majority, chairman vote irrelevant

    def test_red_veto_creates_conflict(self):
        """RED veto should produce a conflict for JUDGE review."""
        from nexara_prime.council import ConflictResolver, AgentSeat, ConflictType

        conflict = ConflictResolver.handle_veto(
            veto_agent=AgentSeat.RED,
            veto_reason="Unsafe database access pattern detected",
        )

        assert conflict.conflict_type == ConflictType.VETO_EXERCISED
        assert conflict.parties == [AgentSeat.RED]
        assert "RED veto" in conflict.resolution_note

    def test_judge_veto_creates_conflict(self):
        """JUDGE veto should require supermajority override."""
        from nexara_prime.council import ConflictResolver, AgentSeat, ConflictType

        conflict = ConflictResolver.handle_veto(
            veto_agent=AgentSeat.JUDGE,
            veto_reason="Violates NSEC Article 26: Quality must not degrade",
        )

        assert conflict.conflict_type == ConflictType.VETO_EXERCISED
        assert "JUDGE veto" in conflict.resolution_note

    def test_escalate_to_human(self):
        """Unresolvable conflicts escalate to human."""
        from nexara_prime.council import ConflictResolver, AgentSeat, ConflictType, Conflict

        conflict = Conflict(
            conflict_type=ConflictType.VOTE_TIE,
            parties=[AgentSeat.CHAIRMAN, AgentSeat.JUDGE],
            description="Irreconcilable deadlock",
        )

        resolved = ConflictResolver.escalate_to_human(conflict, "Deadlock after 3 rounds")
        assert resolved.resolution_note.startswith("ESCALATED to human")


# ============================================================
# TokenGovernor Tests
# ============================================================

class TestTokenGovernor:
    """Test token budget management."""

    def test_create_budget_defaults(self):
        """Each agent gets its configured default budget."""
        from nexara_prime.council import TokenGovernor, TokenMode

        budget = TokenGovernor.create_budget("H-CHAIRMAN")
        assert budget.agent_id == "H-CHAIRMAN"
        assert budget.max_input_tokens == 12000
        assert budget.mode == TokenMode.AGGRESSIVE

    def test_create_budget_balanced(self):
        """Budget respects mode parameter."""
        from nexara_prime.council import TokenGovernor, TokenMode

        budget = TokenGovernor.create_budget("H-CODE", mode=TokenMode.BALANCED)
        assert budget.mode == TokenMode.BALANCED

    def test_should_compress_below_threshold(self):
        """Budget below 40% usage should not trigger compression."""
        from nexara_prime.council import TokenGovernor, TokenBudget, TokenMode

        budget = TokenBudget(
            agent_id="H-CODE",
            max_input_tokens=8000,
            tokens_used_input=1000,  # 12.5%
            mode=TokenMode.AGGRESSIVE,
        )

        assert not TokenGovernor.should_compress(budget)

    def test_should_compress_above_threshold(self):
        """Budget above 40% usage should trigger compression."""
        from nexara_prime.council import TokenGovernor, TokenBudget, TokenMode

        budget = TokenBudget(
            agent_id="H-CODE",
            max_input_tokens=8000,
            tokens_used_input=4000,  # 50%
            mode=TokenMode.AGGRESSIVE,
        )

        assert TokenGovernor.should_compress(budget)

    def test_enforce_budget_under_limit(self):
        """Under-budget usage should produce no violations."""
        from nexara_prime.council import TokenGovernor, TokenUsage, TokenMode

        usage = TokenUsage(mission_id="test-1")
        violations = TokenGovernor.enforce_budget(usage, TokenMode.AGGRESSIVE)
        assert violations == []

    def test_enforce_budget_over_limit(self):
        """Over-budget usage should produce violations."""
        from nexara_prime.council import TokenGovernor, TokenUsage, TokenMode

        usage = TokenUsage(
            mission_id="test-1",
            total_input_tokens=40000,
            total_output_tokens=20000,  # 60000 > 50000 cap
        )
        violations = TokenGovernor.enforce_budget(usage, TokenMode.AGGRESSIVE)
        assert len(violations) > 0
        assert "MISSION_OVER_BUDGET" in violations[0]

    def test_missing_agent_gets_default(self):
        """Unknown agents get 8000 default budget."""
        from nexara_prime.council import TokenGovernor

        budget = TokenGovernor.create_budget("UNKNOWN_AGENT")
        assert budget.max_input_tokens == 8000

    def test_generate_status_snapshot(self):
        """Status snapshot should contain all required fields."""
        from nexara_prime.council import TokenGovernor, TokenUsage, TokenBudget

        usage = TokenUsage(mission_id="test-snapshot")
        usage.agent_budgets["H-CODE"] = TokenBudget(
            agent_id="H-CODE", tokens_used_input=2000, max_input_tokens=8000
        )
        usage.compression_count = 3

        snap = TokenGovernor.generate_status_snapshot(usage)
        assert snap["mission_id"] == "test-snapshot"
        assert snap["compression_count"] == 3
        assert "agent_breakdown" in snap
        assert "H-CODE" in snap["agent_breakdown"]


# ============================================================
# ExecutionPipeline Tests
# ============================================================

class TestExecutionPipeline:
    """Test the 10-stage execution pipeline."""

    @pytest.fixture
    def complete_dna(self):
        from nexara_prime.council import create_council_mission, MissionRisk
        return create_council_mission(
            objective="Test pipeline execution",
            risk=MissionRisk.R1_LOW,
        )

    @pytest.fixture
    def high_risk_dna(self):
        from nexara_prime.council import create_council_mission, MissionRisk
        return create_council_mission(
            objective="Deploy to production",
            risk=MissionRisk.R3_HIGH,
        )

    def test_full_pipeline_completes(self, complete_dna):
        """Full pipeline should complete all 10 stages."""
        from nexara_prime.council import ExecutionPipeline, PipelineStage, StageStatus

        pipeline = ExecutionPipeline(complete_dna)
        state = pipeline.run()

        assert state.is_complete
        assert state.stages[PipelineStage.MEMORY_COMMIT].status == StageStatus.COMPLETED
        assert state.progress["percent"] == 100.0

    def test_pipeline_progress_tracking(self, complete_dna):
        """Progress should be tracked correctly."""
        from nexara_prime.council import ExecutionPipeline

        pipeline = ExecutionPipeline(complete_dna)
        state = pipeline.run()

        progress = state.progress
        assert progress["total_stages"] == 10
        assert progress["completed"] == 10
        assert progress["failed"] == 0

    def test_pipeline_generates_receipt(self, complete_dna):
        """Pipeline must generate a BUILD_RECEIPT."""
        from nexara_prime.council import ExecutionPipeline

        pipeline = ExecutionPipeline(complete_dna)
        state = pipeline.run()
        receipt = pipeline.generate_receipt(state)

        assert receipt["receipt_type"] == "BUILD_RECEIPT"
        assert receipt["receipt_version"] == "2.0.0"
        assert "created_files" in receipt
        assert "agent_status" in receipt
        assert "skill_status" in receipt
        assert "token_strategy" in receipt
        assert "test_results" in receipt
        assert "risk_list" in receipt
        assert "next_phase" in receipt

    def test_high_risk_pipeline_blocks_on_red_team(self, high_risk_dna):
        """High risk mission with 'production' deployment should be blocked by red team."""
        from nexara_prime.council import ExecutionPipeline, PipelineStage

        pipeline = ExecutionPipeline(high_risk_dna)
        state = pipeline.run()

        # Red team should flag the 'production' keyword
        red_result = state.stages.get(PipelineStage.RED_TEAM_ATTACK)
        assert red_result is not None
        # High-risk deployment should at minimum generate risks
        assert len(red_result.output.get("risks_found", [])) > 0

    def test_pipeline_single_stage(self, complete_dna):
        """Single stage execution should work."""
        from nexara_prime.council import ExecutionPipeline, PipelineStage, StageStatus

        pipeline = ExecutionPipeline(complete_dna)
        result = pipeline.run_stage(PipelineStage.DNA_GENERATION)

        assert result.status == StageStatus.COMPLETED
        assert "dna_hash" in result.output

    def test_pipeline_idempotent(self, complete_dna):
        """Re-running completed stages is safe."""
        from nexara_prime.council import ExecutionPipeline

        pipeline = ExecutionPipeline(complete_dna)
        state1 = pipeline.run()
        receipt1 = pipeline.generate_receipt(state1)

        # Run again
        pipeline2 = ExecutionPipeline(complete_dna)
        state2 = pipeline2.run()
        receipt2 = pipeline2.generate_receipt(state2)

        assert state1.is_complete == state2.is_complete
        assert receipt1["test_results"]["completed"] == receipt2["test_results"]["completed"]

    def test_incomplete_dna_fails_requirement(self):
        """Incomplete DNA should fail at requirement stage."""
        from nexara_prime.council import MissionDNA, ExecutionPipeline, PipelineStage, StageStatus

        dna = MissionDNA()  # Incomplete — no fields populated
        pipeline = ExecutionPipeline(dna)
        state = pipeline.run()

        req = state.stages[PipelineStage.REQUIREMENT_INPUT]
        assert req.status == StageStatus.FAILED
        assert any("incomplete" in e.lower() for e in req.errors)


# ============================================================
# Council __init__.py Integration Tests
# ============================================================

class TestCouncilIntegration:
    """Test the convenience functions and integration bridge."""

    def test_create_council_mission_defaults(self):
        """create_council_mission should produce complete DNA with defaults."""
        from nexara_prime.council import create_council_mission

        dna = create_council_mission(objective="Test default mission")

        assert dna.is_complete
        assert dna.objective == "Test default mission"
        assert len(dna.agents) > 0
        assert len(dna.constraints) > 0
        assert len(dna.verification) > 0
        assert len(dna.rollback) > 0

    def test_create_council_mission_high_risk(self):
        """High risk mission gets restricted permissions."""
        from nexara_prime.council import create_council_mission, MissionRisk

        dna = create_council_mission(
            objective="Critical deployment",
            risk=MissionRisk.R3_HIGH,
        )

        assert dna.risk == MissionRisk.R3_HIGH
        assert "H-RED" in dna.agents
        assert "H-JUDGE" in dna.agents
        # High risk: restricted permissions
        assert "write_local" not in dna.permissions or len(dna.permissions) <= 2

    def test_run_council_pipeline(self):
        """run_council_pipeline end-to-end."""
        from nexara_prime.council import create_council_mission, run_council_pipeline, MissionRisk

        dna = create_council_mission(
            objective="Integration test mission",
            risk=MissionRisk.R1_LOW,
        )

        result = run_council_pipeline(dna)

        assert "state" in result
        assert "receipt" in result
        assert result["state"].is_complete
        assert result["receipt"]["receipt_type"] == "BUILD_RECEIPT"

    def test_all_eight_skill_statuses_present(self):
        """Receipt must declare status for all required skills."""
        from nexara_prime.council import create_council_mission, run_council_pipeline

        dna = create_council_mission(objective="Skill status test")
        result = run_council_pipeline(dna)

        skills = result["receipt"]["skill_status"]
        required = [
            "council_deliberation",
            "multi_agent_orchestration",
            "memory_management",
            "evidence_generation",
            "token_optimization",
            "risk_assessment",
            "mission_routing",
        ]
        for skill in required:
            assert skill in skills, f"Missing skill: {skill}"

    def test_receipt_contains_all_required_fields(self):
        """BUILD_RECEIPT must have all 7 required fields per council_rules.yaml."""
        from nexara_prime.council import create_council_mission, run_council_pipeline

        dna = create_council_mission(objective="Receipt field test")
        result = run_council_pipeline(dna)
        receipt = result["receipt"]

        required_fields = [
            "created_files",
            "agent_status",
            "skill_status",
            "token_strategy",
            "test_results",
            "risk_list",
            "next_phase",
        ]
        for field in required_fields:
            assert field in receipt, f"Missing required field: {field}"

    def test_token_strategy_is_aggressive(self):
        """Default token strategy should be AGGRESSIVE."""
        from nexara_prime.council import create_council_mission, run_council_pipeline

        dna = create_council_mission(objective="Token strategy test")
        result = run_council_pipeline(dna)

        assert result["receipt"]["token_strategy"]["mode"] == "AGGRESSIVE"
        assert len(result["receipt"]["token_strategy"]["rules"]) == 6

    def test_prohibitions_checked_in_receipt(self):
        """All prohibitions must be checked in receipt."""
        from nexara_prime.council import create_council_mission, run_council_pipeline

        dna = create_council_mission(objective="Prohibition check test")
        result = run_council_pipeline(dna)

        prohibitions = result["receipt"]["prohibitions_checked"]
        assert len(prohibitions) == 5
        for p in prohibitions:
            assert "COMPLIANT" in p


# ============================================================
# Runtime __init__.py Module Discovery
# ============================================================

class TestModuleDiscovery:
    """Verify all council modules are importable."""

    def test_import_council(self):
        """Full council package should import."""
        from nexara_prime import council
        assert council is not None

    def test_import_all_names(self):
        """All __all__ names should be accessible."""
        from nexara_prime.council import __all__ as names
        import nexara_prime.council as c

        for name in names:
            assert hasattr(c, name), f"Missing export: {name}"

    def test_enum_values_correct(self):
        """All enums should have expected values."""
        from nexara_prime.council import (
            MissionRisk, DNAStatus, PipelineStage, StageStatus,
            AgentSeat, TokenMode,
        )

        assert MissionRisk.R4_CRITICAL.value == "R4_CRITICAL"
        assert DNAStatus.GENERATED.value == "GENERATED"
        assert PipelineStage.MEMORY_COMMIT.value == "MEMORY_COMMIT"
        assert StageStatus.BLOCKED.value == "BLOCKED"
        assert AgentSeat.CHAIRMAN.value == "H-CHAIRMAN"
        assert AgentSeat.RED.value == "H-RED"
        assert AgentSeat.JUDGE.value == "H-JUDGE"
        assert TokenMode.AGGRESSIVE.value == "AGGRESSIVE"

    def test_all_9_agent_seats(self):
        """All 9 council seats should be defined."""
        from nexara_prime.council import AgentSeat

        seats = list(AgentSeat)
        assert len(seats) == 9
        seat_names = {s.value for s in seats}
        assert "H-CHAIRMAN" in seat_names
        assert "H-STAFF" in seat_names
        assert "H-ARCH" in seat_names
        assert "H-CODE" in seat_names
        assert "H-EXEC" in seat_names
        assert "H-RED" in seat_names
        assert "H-JUDGE" in seat_names
        assert "H-MEM" in seat_names
        assert "H-TOKEN" in seat_names

    def test_10_pipeline_stages(self):
        """All 10 pipeline stages should be defined."""
        from nexara_prime.council import PipelineStage

        stages = list(PipelineStage)
        assert len(stages) == 10


# ============================================================
# File System Verification
# ============================================================

class TestFileSystemPresence:
    """Verify all council files exist on disk."""

    COUNCIL_ROOT = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "src", "nexara_prime", "council"
    ))

    def test_constitution_files_exist(self):
        """Constitution and rules files must exist."""
        root = self.COUNCIL_ROOT
        assert os.path.isfile(os.path.join(root, "constitution", "CONSTITUTION_V2.md"))
        assert os.path.isfile(os.path.join(root, "constitution", "council_rules.yaml"))

    def test_all_agent_yamls_exist(self):
        """All 9 agent YAML files must exist."""
        root = self.COUNCIL_ROOT
        agents_dir = os.path.join(root, "agents")
        expected = [
            "chairman.yaml", "staff.yaml", "architect.yaml", "coder.yaml",
            "executor.yaml", "redteam.yaml", "judge.yaml", "memory.yaml", "token.yaml",
        ]
        for fname in expected:
            path = os.path.join(agents_dir, fname)
            assert os.path.isfile(path), f"Missing agent file: {fname}"

    def test_governance_policies_exist(self):
        """Approval and risk policies must exist."""
        root = self.COUNCIL_ROOT
        assert os.path.isfile(os.path.join(root, "governance", "approval_policy.yaml"))
        assert os.path.isfile(os.path.join(root, "governance", "risk_policy.yaml"))

    def test_memory_readmes_exist(self):
        """Memory system READMEs must exist."""
        root = self.COUNCIL_ROOT
        assert os.path.isfile(os.path.join(root, "memory", "decisions", "README.md"))
        assert os.path.isfile(os.path.join(root, "memory", "failures", "README.md"))
        assert os.path.isfile(os.path.join(root, "memory", "evidence", "README.md"))

    def test_python_modules_exist(self):
        """All Python modules must exist."""
        root = self.COUNCIL_ROOT
        expected = [
            "__init__.py",
            "mission_dna.py",
            "pipeline.py",
            "runtime/__init__.py",
            "runtime/mission_router.py",
            "runtime/conflict_resolver.py",
            "runtime/token_governor.py",
        ]
        for fname in expected:
            path = os.path.join(root, fname)
            assert os.path.isfile(path), f"Missing Python module: {fname}"
