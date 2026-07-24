"""Cross-module enum wire truth tests: SDK must match Core exactly.

Uses real runtime imports (not AST parsing). AST parsing is a supplementary
static drift guard.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ═══ Helpers ═══

def _core_enum(name: str) -> dict[str, str]:
    from nexara_prime import models
    return {m.name: m.value for m in getattr(models, name)}


def _sdk_enum(name: str) -> dict[str, str]:
    from nexara_sdk import models
    return {m.name: m.value for m in getattr(models, name)}


def _ast_sdk_enum(name: str) -> dict[str, str]:
    """Parse SDK source as static drift guard."""
    src = (REPO / "platform/sdk/python/nexara_sdk/models.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            members = {}
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                            if isinstance(item.value.value, str):
                                members[target.id] = item.value.value
            return members
    return {}


# ═══ RuntimeRole (P1 fix: values were lowercase, now PascalCase) ═══

class TestRuntimeRoleWireTruth:

    def test_names_equal_runtime(self) -> None:
        assert set(_core_enum("RuntimeRole").keys()) == set(_sdk_enum("RuntimeRole").keys())

    def test_values_equal_runtime(self) -> None:
        c = _core_enum("RuntimeRole")
        s = _sdk_enum("RuntimeRole")
        assert c == s, f"Core: {c}\nSDK:  {s}"

    def test_json_serialization_equal_runtime(self) -> None:
        from nexara_prime.models import RuntimeRole as CoreRole
        from nexara_sdk.models import RuntimeRole as SdkRole
        for name in _core_enum("RuntimeRole"):
            assert CoreRole[name].value == SdkRole[name].value

    def test_planstep_round_trip_runtime_role(self) -> None:
        """Real SDK model round-trip: role field preserves wire value."""
        from nexara_sdk.models import PlanStep
        original = {
            "step_id": "step_1", "title": "test",
            "role": "Executor", "persona": "Nexara", "status": "pending",
        }
        model = PlanStep.model_validate(original)
        serialized = model.model_dump(mode="json")
        assert serialized["role"] == "Executor", f"role wire mismatch: {serialized['role']}"
        assert serialized["persona"] == "Nexara"
        reparsed = PlanStep.model_validate(serialized)
        assert reparsed.model_dump(mode="json") == serialized


# ═══ Related enums (runtime imports) ═══

class TestAllRelatedEnumsRuntime:
    def test_mission_state_equal(self) -> None:
        assert _core_enum("MissionState") == _sdk_enum("MissionState")

    def test_risk_level_equal(self) -> None:
        assert _core_enum("RiskLevel") == _sdk_enum("RiskLevel")

    def test_persona_equal(self) -> None:
        assert _core_enum("Persona") == _sdk_enum("Persona")

    def test_approval_status_equal(self) -> None:
        assert _core_enum("ApprovalStatus") == _sdk_enum("ApprovalStatus")

    def test_memory_kind_equal(self) -> None:
        assert _core_enum("MemoryKind") == _sdk_enum("MemoryKind")


# ═══ AST static drift guards (supplementary, not primary) ═══

class TestASTStaticDriftGuard:
    def test_runtime_role_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("RuntimeRole") == _core_enum("RuntimeRole")

    def test_mission_state_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("MissionState") == _core_enum("MissionState")

    def test_risk_level_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("RiskLevel") == _core_enum("RiskLevel")

    def test_persona_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("Persona") == _core_enum("Persona")

    def test_approval_status_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("ApprovalStatus") == _core_enum("ApprovalStatus")

    def test_memory_kind_source_matches_runtime(self) -> None:
        assert _ast_sdk_enum("MemoryKind") == _core_enum("MemoryKind")
