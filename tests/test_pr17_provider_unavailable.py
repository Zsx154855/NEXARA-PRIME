"""
Test: PROVIDER UNAVAILABLE PATH (PR17).

When mock_model=False AND no real provider configured (model_provider='none' or empty),
the runtime MUST NOT call MockProvider for actual execution. It must NOT produce fake
output, must NOT enter COMPLETED. It must go to PROVIDER_UNAVAILABLE or FAILED_RECOVERABLE.

Checks:
1. Snapshot provider is NOT 'mock'
2. Snapshot has provider_unavailable=True
3. Snapshot has recovery_pointer (rollback_point)
4. Calling run_mission raises ProviderUnavailable (does not complete with fake data)
5. Mission state is NOT Completed after attempting run_mission
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.model_gateway import ProviderUnavailable
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.config import Settings


def _unavailable_runtime() -> NexaraRuntime:
    """Create a runtime with no real provider and mock_model=False."""
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="none",
        mock_model=False,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


def _unavailable_runtime_empty_provider() -> NexaraRuntime:
    """Create a runtime with empty provider string and mock_model=False."""
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="",
        mock_model=False,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


class TestProviderUnavailablePath:
    """PROVIDER UNAVAILABLE PATH — PR17 verification."""

    # ── 1. Structural checks at init ────────────────────────────────────

    def test_unavailable_provider_is_not_mock(self) -> None:
        """When mock_model=False + model_provider='none', provider is UnavailableProvider, not MockProvider."""
        rt = _unavailable_runtime()
        # The provider is a structural placeholder, but its name is NOT 'mock'
        assert rt.models.provider is not None
        assert rt.models.provider.name != "mock", (
            f"Expected provider name NOT to be 'mock', got '{rt.models.provider.name}'"
        )
        assert rt.models.provider.name == "unavailable"

    def test_unavailable_provider_is_not_mock_empty_provider(self) -> None:
        """Same check when model_provider=''."""
        rt = _unavailable_runtime_empty_provider()
        assert rt.models.provider.name != "mock"
        assert rt.models.provider.name == "unavailable"

    def test_provider_unavailable_flag_is_set(self) -> None:
        """_provider_unavailable is True when no real provider configured."""
        rt = _unavailable_runtime()
        assert getattr(rt, '_provider_unavailable', False) is True

    def test_provider_unavailable_flag_empty_provider(self) -> None:
        """_provider_unavailable is True when model_provider=''."""
        rt = _unavailable_runtime_empty_provider()
        assert getattr(rt, '_provider_unavailable', False) is True

    # ── 2. Snapshot checks ─────────────────────────────────────────────

    def test_snapshot_does_not_report_mock(self) -> None:
        """Snapshot provider field must not be 'mock'."""
        rt = _unavailable_runtime()
        mission = rt.create_mission("Test no mock provider")
        snapshot = rt.inspect_mission(mission.mission_id)
        assert snapshot["provider"] != "mock", (
            f"Snapshot reports provider='mock', should be 'unavailable' or similar. Got: {snapshot['provider']}"
        )

    def test_snapshot_has_provider_unavailable_flag(self) -> None:
        """Snapshot must include provider_unavailable=True."""
        rt = _unavailable_runtime()
        mission = rt.create_mission("Test provider unavailable flag")
        snapshot = rt.inspect_mission(mission.mission_id)
        assert snapshot.get("provider_unavailable") is True, (
            f"Expected provider_unavailable=True in snapshot, got: {snapshot.get('provider_unavailable')}"
        )

    def test_snapshot_has_retryability(self) -> None:
        """Snapshot must include retry_count field."""
        rt = _unavailable_runtime()
        mission = rt.create_mission("Test retryability")
        snapshot = rt.inspect_mission(mission.mission_id)
        # retry_count should exist (defaults to 0)
        assert "retry_count" in snapshot, "Snapshot missing retry_count"

    def test_snapshot_has_recovery_pointer(self) -> None:
        """Snapshot must include recovery_pointer field."""
        rt = _unavailable_runtime()
        mission = rt.create_mission("Test recovery pointer")
        snapshot = rt.inspect_mission(mission.mission_id)
        assert "recovery_pointer" in snapshot, "Snapshot missing recovery_pointer"
        # At this stage, rollback_point might be None — the field must exist

    # ── 3. Execution path — run_mission must NOT complete with fake data ──

    def test_run_mission_raises_or_fails_not_completed(self) -> None:
        """run_mission must NOT produce COMPLETED state when provider is unavailable.
        It must raise ProviderUnavailable or the mission must end in Failed/Blocked."""
        rt = _unavailable_runtime()
        mission = rt.create_mission("Test no mock execution")

        # Move through the pipeline to Execution state
        planned = rt.plan_mission(mission.mission_id)
        assert planned.state == "Approval"

        approved = rt.approve_mission(
            mission.mission_id, approved=True, actor="human",
            note="Test: attempting run with no provider."
        )
        assert approved.state == "Execution"

        # Now run — this should raise ProviderUnavailable (NOT produce completed mission)
        with pytest.raises(ProviderUnavailable) as excinfo:
            rt.run_mission(mission.mission_id)

        # Verify the error mentions no_provider_configured
        error_text = str(excinfo.value)
        assert "no_provider_configured" in error_text or "unavailable" in error_text.lower(), (
            f"Unexpected error message: {error_text}"
        )

        # After the exception, reload mission — state must NOT be Completed
        failed_mission = rt.get_mission(mission.mission_id)
        assert failed_mission.state != "Completed", (
            f"Mission state should NOT be Completed when provider unavailable. Got: {failed_mission.state}"
        )
        # ProviderUnavailable is recoverable — mission stays resumable, not terminal
        assert failed_mission.state in {"Failed", "Blocked", "Execution"}, (
            f"Expected resumable/terminal state, got: {failed_mission.state}"
        )

    # ── 4. Provider name at ModelGateway level ──

    def test_gateway_provider_name_is_unavailable(self) -> None:
        """ModelGateway.provider.name should be 'unavailable'."""
        rt = _unavailable_runtime()
        assert rt.models.provider.name == "unavailable"

    def test_direct_unavailable_provider_raises(self) -> None:
        """Calling UnavailableProvider.complete() directly raises ProviderUnavailable."""
        from nexara_prime.model_gateway import UnavailableProvider
        provider = UnavailableProvider()
        assert provider.name == "unavailable"
        with pytest.raises(ProviderUnavailable) as excinfo:
            provider.complete("system", "task", trace_id="test")
        assert "no_provider_configured" in str(excinfo.value)

    # ── 5. Verify MockProvider is never called down this path ──

    def test_mock_provider_not_in_gateway(self) -> None:
        """The ModelGateway must NOT use MockProvider when mock_model=False + no real provider."""
        rt = _unavailable_runtime()
        from nexara_prime.model_gateway import MockProvider, UnavailableProvider
        assert not isinstance(rt.models.provider, MockProvider), (
            "ModelGateway should NOT contain MockProvider in unavailable path"
        )
        assert isinstance(rt.models.provider, UnavailableProvider), (
            f"Expected UnavailableProvider, got {type(rt.models.provider).__name__}"
        )

    def test_mock_provider_not_in_gateway_empty(self) -> None:
        """Same check for empty provider string."""
        rt = _unavailable_runtime_empty_provider()
        from nexara_prime.model_gateway import MockProvider, UnavailableProvider
        assert not isinstance(rt.models.provider, MockProvider)
        assert isinstance(rt.models.provider, UnavailableProvider)
