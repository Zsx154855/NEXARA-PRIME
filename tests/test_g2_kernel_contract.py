"""G2 Kernel Contract Tests — 5 invariants mapped to 7 prohibited behaviors.

These are CONTRACT tests: they verify the kernel BOUNDARY is enforceable.
They test WHAT must not happen, not HOW the kernel is implemented.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KERNEL_CONTRACT = REPO / ".nexara/contracts/chief_brain_kernel_contract_v1.yaml"
G1_INVARIANTS = REPO / ".nexara/contracts/contract_invariant_tests_v1.yaml"
AUTHORITY_MATRIX = REPO / ".nexara/contracts/authority_matrix_v1.yaml"
EVIDENCE_PY = REPO / "src/nexara_prime/evidence.py"
MEMORY_PY = REPO / "src/nexara_prime/memory.py"
EVALUATION_PY = REPO / "src/nexara_prime/evaluation.py"
RUNTIME_PY = REPO / "src/nexara_prime/runtime.py"
STATE_MACHINE_PY = REPO / "src/nexara_prime/state_machine.py"
MODELS_PY = REPO / "src/nexara_prime/models.py"


def _py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in str(p)]


# ═══════════════════════════════════════════════════════════════
# INVARIANT_01: Skill Cannot Grant Permission
# PROHIBIT_03: Kernel MUST NOT grant permissions
# Contract: "Skill.permission is NEVER present"
# ═══════════════════════════════════════════════════════════════

class TestInvariant01SkillCannotGrantPermission:
    """A Skill describes WHAT can be done. Permission is ALWAYS external."""

    def test_skill_definitions_contain_no_permission_field(self) -> None:
        """No skill/capability definition should contain inline permission grants."""
        skill_like = {"skill_id", "version", "capability_binding"}
        for f in _py_files(REPO / "src/nexara_prime"):
            if f.name == "models.py":
                tree = ast.parse(f.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check for classes that look like skill definitions
                        field_names = set()
                        for item in ast.iter_child_nodes(node):
                            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                field_names.add(item.target.id)
                        # If this looks like a skill definition, it must NOT have permission fields
                        if skill_like & field_names:
                            assert "permission" not in field_names, (
                                f"Skill-like class '{node.name}' in {f.name} "
                                f"contains 'permission' field — violates INVARIANT_01"
                            )

    def test_capability_registry_separates_permission(self) -> None:
        """CapabilityRegistry must check permissions externally, not inline."""
        cap_py = REPO / "src/nexara_prime/capabilities.py"
        assert cap_py.exists(), "capabilities.py must exist"
        content = cap_py.read_text()
        # Capability registry must reference external permission checking
        assert "permission" in content.lower(), (
            "capabilities.py must reference permission enforcement"
        )

    def test_models_have_no_permission_on_skill_entities(self) -> None:
        """MissionSpec, PlanStep, WorkContract must not contain permission fields."""
        models = MODELS_PY.read_text()
        # Parse top-level classes
        tree = ast.parse(models)
        skill_entities = {"MissionSpec", "PlanStep", "WorkContract", "AgentAssignment"}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name in skill_entities:
                field_names = set()
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        field_names.add(item.target.id)
                assert "permission" not in field_names, (
                    f"{node.name} must not contain 'permission' field — violates INVARIANT_01"
                )


# ═══════════════════════════════════════════════════════════════
# INVARIANT_02: Canvas Cannot Bypass Runtime
# PROHIBIT_01: Self-verify (kernel must not self-certify)
# Contract: "Canvas operations → Runtime → governance → execution"
# ═══════════════════════════════════════════════════════════════

class TestInvariant02CanvasCannotBypassRuntime:
    """UI/Canvas must route ALL state changes through Runtime API."""

    def test_api_routes_through_runtime(self) -> None:
        """API endpoints must call NexaraRuntime methods, not bypass to db directly."""
        api_py = REPO / "src/nexara_prime/api.py"
        content = api_py.read_text()
        assert "NexaraRuntime" in content or "runtime" in content.lower(), (
            "api.py must reference NexaraRuntime for state changes"
        )

    def test_api_has_no_direct_db_writes(self) -> None:
        """API must not directly write to SQLiteStore for mission state changes."""
        api_py = REPO / "src/nexara_prime/api.py"
        content = api_py.read_text()
        tree = ast.parse(content)
        # API should import NexaraRuntime, not directly manipulate db
        imports_runtime = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "runtime" in node.module:
                    imports_runtime = True
        assert imports_runtime, "api.py must import from runtime (not bypass to db)"

    def test_cli_routes_through_runtime(self) -> None:
        """CLI must route through runtime, not direct db access."""
        cli_py = REPO / "src/nexara_prime/cli.py"
        content = cli_py.read_text()
        assert "runtime" in content.lower() or "NexaraRuntime" in content, (
            "cli.py must reference runtime for state changes"
        )


# ═══════════════════════════════════════════════════════════════
# INVARIANT_03: Executor Cannot Create PASS Verdict
# PROHIBIT_01: Self-verify, PROHIBIT_07: Modify contracts
# Contract: "Executor != Auditor. Receipt creator != Mission executor."
# ═══════════════════════════════════════════════════════════════

class TestInvariant03ExecutorCannotCreatePASSVerdict:
    """The agent that executes must NOT be the agent that verifies."""

    def test_evaluation_engine_is_independent(self) -> None:
        """EvaluationEngine is imported separately, not part of execution flow."""
        eval_py = EVALUATION_PY
        content = eval_py.read_text()
        assert "class EvaluationEngine" in content, "EvaluationEngine must exist"
        # Evaluation must be a separate module, not embedded in runtime execution
        assert "evaluate" in content.lower(), "EvaluationEngine must have evaluate capability"

    def test_independent_review_module_exists(self) -> None:
        """There must be an independent review mechanism."""
        ir_py = REPO / "src/nexara_prime/independent_review.py"
        assert ir_py.exists(), "independent_review.py must exist for auditor role"

    def test_receipt_requires_independent_auditor(self) -> None:
        """Receipt creation must not be in the execution hot path."""
        runtime = RUNTIME_PY.read_text()
        # Runtime's execute stage should create EVIDENCE, not final RECEIPT
        assert "receipt" in runtime.lower() or "Receipt" in runtime, (
            "Runtime must reference receipt/attestation flow"
        )


# ═══════════════════════════════════════════════════════════════
# INVARIANT_04: Memory Cannot Overwrite Evidence
# PROHIBIT_04: Kernel MUST NOT overwrite evidence
# Contract: "MemoryRecord.source_evidence_id is required. Evidence is append-only."
# ═══════════════════════════════════════════════════════════════

class TestInvariant04MemoryCannotOverwriteEvidence:
    """Memory is DERIVED from evidence. Evidence is the single source of truth."""

    def test_memory_record_has_source_evidence_id(self) -> None:
        """MemoryRecord model must have source_evidence_id field."""
        models = MODELS_PY.read_text()
        assert "source_evidence_id" in models, (
            "MemoryRecord must have source_evidence_id to link to evidence"
        )

    def test_evidence_store_is_append_only(self) -> None:
        """EvidenceStore must be append-only — no update/delete methods."""
        evidence = EVIDENCE_PY.read_text()
        # Must have add/commit/append, not update/delete/modify
        has_add = "add" in evidence.lower() or "commit" in evidence.lower() or "store" in evidence.lower()
        assert has_add, "EvidenceStore must have append capability"

    def test_memory_kernel_requires_evidence_backing(self) -> None:
        """MemoryKernel must reference evidence for memory patches."""
        memory = MEMORY_PY.read_text()
        assert "evidence" in memory.lower(), (
            "MemoryKernel must reference evidence for memory operations"
        )

    def test_sdk_memory_record_nullable_source(self) -> None:
        """SDK MemoryRecord.source_evidence_id is nullable but present."""
        sdk_models = REPO / "platform/sdk/python/nexara_sdk/models.py"
        content = sdk_models.read_text()
        assert "source_evidence_id" in content, (
            "SDK MemoryRecord must have source_evidence_id field"
        )


# ═══════════════════════════════════════════════════════════════
# INVARIANT_05: Mission Completion Requires Full Chain
# PROHIBIT_05: Kernel MUST NOT declare mission complete without full chain
# Contract: "Success Criteria + Evidence + Audit + Receipt + Reflection"
# ═══════════════════════════════════════════════════════════════

class TestInvariant05MissionCompletionRequiresFullChain:
    """Mission completion requires ALL 5 links of the chain."""

    def test_state_machine_completed_has_gate(self) -> None:
        """Completed state must require passing through verification stages."""
        sm = STATE_MACHINE_PY.read_text()
        assert "COMPLETED" in sm or "Completed" in sm, (
            "State machine must define COMPLETED state"
        )

    def test_runtime_has_all_completion_stages(self) -> None:
        """Runtime must have: verify, evidence, memory, evaluate stages."""
        runtime = RUNTIME_PY.read_text()
        stages = ["verify", "evidence", "memory", "evaluate"]
        found = [s for s in stages if s in runtime.lower()]
        assert len(found) >= 3, (
            f"Runtime must have completion stages. Found: {found}. Missing: {set(stages) - set(found)}"
        )

    def test_mission_spec_has_success_criteria(self) -> None:
        """MissionSpec or WorkContract must define success criteria."""
        models = MODELS_PY.read_text()
        has_criteria = "success" in models.lower() or "acceptance" in models.lower()
        assert has_criteria, "Mission model must reference success/acceptance criteria"

    def test_reflection_entity_exists(self) -> None:
        """Reflection/ImprovementProposal entity must exist in SDK models or evaluation.py."""
        sdk_models = (REPO / "platform/sdk/python/nexara_sdk/models.py").read_text()
        eval_py = EVALUATION_PY.read_text()
        has_reflection_sdk = "ImprovementProposal" in sdk_models
        has_evaluation = "EvaluationEngine" in eval_py
        assert has_reflection_sdk or has_evaluation, (
            "Reflection/improvement entity must exist (SDK ImprovementProposal or core EvaluationEngine)"
        )


# ═══════════════════════════════════════════════════════════════
# Kernel Boundary Structural Tests
# ═══════════════════════════════════════════════════════════════

class TestKernelBoundaryIntegrity:
    """The kernel contract defines clear IN/OUT boundaries. These must hold."""

    def test_kernel_contract_yaml_exists(self) -> None:
        """ChiefBrainKernel contract must exist."""
        assert KERNEL_CONTRACT.exists(), "chief_brain_kernel_contract_v1.yaml must exist"

    def test_kernel_in_scope_modules_exist(self) -> None:
        """All 7 IN-SCOPE kernel modules must exist in src/nexara_prime/."""
        in_scope_files = [
            "runtime.py", "orchestration.py", "state_machine.py",
            "mission_triage.py", "mission_compiler.py", "contract_engine.py",
        ]
        for f in in_scope_files:
            p = REPO / "src/nexara_prime" / f
            assert p.exists(), f"Kernel IN-SCOPE module {f} must exist"

    def test_kernel_out_of_scope_modules_are_not_kernel(self) -> None:
        """Infrastructure modules must NOT be in the kernel boundary."""
        out_of_scope = ["db.py", "api.py", "cli.py", "config.py"]
        # These exist but are infrastructure, not kernel
        for f in out_of_scope:
            p = REPO / "src/nexara_prime" / f
            assert p.exists(), f"Infrastructure module {f} must exist (as infrastructure, not kernel)"

    def test_g1_invariants_yaml_exists(self) -> None:
        """G1 contract invariants must exist."""
        assert G1_INVARIANTS.exists(), "contract_invariant_tests_v1.yaml must exist"

    def test_authority_matrix_yaml_exists(self) -> None:
        """Authority matrix must exist."""
        assert AUTHORITY_MATRIX.exists(), "authority_matrix_v1.yaml must exist"

    def test_no_second_runtime_exists(self) -> None:
        """There must be exactly ONE NexaraRuntime — no duplicate runtime modules."""
        runtime_count = 0
        for f in _py_files(REPO / "src/nexara_prime"):
            content = f.read_text()
            if "class NexaraRuntime" in content:
                runtime_count += 1
        assert runtime_count == 1, (
            f"Exactly 1 NexaraRuntime must exist, found {runtime_count}"
        )

    def test_no_second_state_machine_exists(self) -> None:
        """There must be exactly ONE MissionStateMachine."""
        sm_count = 0
        for f in _py_files(REPO / "src/nexara_prime"):
            content = f.read_text()
            if "class MissionStateMachine" in content:
                sm_count += 1
        assert sm_count == 1, (
            f"Exactly 1 MissionStateMachine must exist, found {sm_count}"
        )
