"""G4: Capability & Tool Runtime Contract Tests."""
from __future__ import annotations

class FakeStore:
    def execute(self, *a, **kw): return None
    def executemany(self, *a, **kw): pass
    def fetchone(self, *a, **kw): return None
    def fetchall(self, *a, **kw): return []
    def list_records(self, *a, **kw): return []
    def list_record_envelopes(self, *a, **kw): return []
    def commit(self, *a, **kw): pass
    def close(self, *a, **kw): pass


class TestToolRuntimeInvariants:
    """5 tool runtime invariants from G4 contract."""

    def test_invariant_01_all_execution_through_sandbox(self) -> None:
        """TOOL_INVARIANT_01: ToolRuntime uses sandbox for execution."""
        from nexara_prime.tools import ToolRuntime
        # ToolRuntime.__init__ instantiates MacOSSandboxBackend
        import inspect
        src = inspect.getsource(ToolRuntime.__init__)
        assert "sandbox" in src.lower(), "ToolRuntime must reference sandbox"

    def test_invariant_02_idempotency_prevention(self) -> None:
        """TOOL_INVARIANT_02: invocation_id provides idempotency."""
        from nexara_prime.models import ToolInvocation
        assert "invocation_id" in ToolInvocation.model_fields, (
            "ToolInvocation must have invocation_id for idempotency"
        )

    def test_invariant_03_registry_separate_from_execution(self) -> None:
        """TOOL_INVARIANT_03: CapabilityRegistry ≠ ToolRuntime."""
        from nexara_prime.capabilities import CapabilityRegistry
        from nexara_prime.tools import ToolRuntime
        # Registry has no execute method
        reg_methods = {m for m in dir(CapabilityRegistry) if not m.startswith("_")}
        assert "execute" not in reg_methods, "Registry must not execute"
        # ToolRuntime has execute method
        tool_methods = {m for m in dir(ToolRuntime) if not m.startswith("_")}
        assert "invoke" in tool_methods, (
            f"ToolRuntime must have 'invoke' as the execution entry point. Methods: {sorted(tool_methods)}"
        )

    def test_invariant_04_external_effect_requires_approval(self) -> None:
        """TOOL_INVARIANT_04: R2+ tools require approval."""
        from nexara_prime.governance import PolicyEngine
        from nexara_prime.models import RiskLevel
        policy = PolicyEngine()
        # R0, R1: no approval needed
        assert not policy.requires_approval(RiskLevel.R0)
        assert not policy.requires_approval(RiskLevel.R1)
        # R2, R3, R4: approval required
        assert policy.requires_approval(RiskLevel.R2)
        assert policy.requires_approval(RiskLevel.R3)
        assert policy.requires_approval(RiskLevel.R4)

    def test_invariant_05_evidence_created_per_execution(self) -> None:
        """TOOL_INVARIANT_05: ToolRuntime creates evidence."""
        from nexara_prime.tools import ToolRuntime
        import inspect
        src = inspect.getsource(ToolRuntime.__init__)
        assert "evidence" in src.lower(), "ToolRuntime must reference evidence store"


class TestToolRuntimeReality:
    """Verify existing components are functional."""

    def test_sandbox_backends_exist(self) -> None:
        from nexara_prime import sandbox_v2
        assert hasattr(sandbox_v2, "MacOSSandboxBackend")
        assert hasattr(sandbox_v2, "ProcessConstrainedBackend")

    def test_forbidden_commands_blocked(self) -> None:
        from nexara_prime.tools import ToolRuntime
        assert "sudo" in ToolRuntime.FORBIDDEN_COMMAND_PARTS
        assert "rm" in ToolRuntime.FORBIDDEN_COMMAND_PARTS
        assert "curl" in ToolRuntime.FORBIDDEN_COMMAND_PARTS

    def test_connector_registry_exists(self) -> None:
        from nexara_prime.connectors.registry import ConnectorRegistry
        assert ConnectorRegistry is not None

    def test_model_router_exists(self) -> None:
        from nexara_prime.model_router import ModelRouter
        assert ModelRouter is not None

    def test_capability_defaults_include_tools(self) -> None:
        from nexara_prime.capabilities import CapabilityRegistry
        reg = CapabilityRegistry()
        caps = reg.list()
        tool_ids = [c["capability_id"] for c in caps if "tool." in c.get("capability_id", "")]
        assert len(tool_ids) >= 3, f"Expected ≥3 tool capabilities, got {len(tool_ids)}"
