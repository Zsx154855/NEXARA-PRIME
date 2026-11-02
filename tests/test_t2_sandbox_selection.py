"""T2 acceptance: backend selection is explicit and never lies about isolation."""
from __future__ import annotations

from nexara_prime.sandbox_v2 import (
    ProcessConstrainedBackend,
    SandboxInvocation,
    UnavailableSandboxBackend,
    select_sandbox_backend,
)


def test_default_is_fail_closed(monkeypatch):
    import nexara_prime.sandbox_v2 as sb

    monkeypatch.setattr(sb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sb.shutil, "which", lambda _name: None)
    monkeypatch.delenv("NEXARA_SANDBOX_ALLOW_PROCESS_FALLBACK", raising=False)
    backend = select_sandbox_backend("/tmp", allow_process_fallback=False)
    assert isinstance(backend, UnavailableSandboxBackend)
    assert backend.probe_capability().sandbox_mechanism == "none"
    receipt = backend.execute(SandboxInvocation(argv=["echo", "hi"], cwd="/tmp", timeout=5))
    assert receipt.error and "NEXARA_SANDBOX_ALLOW_PROCESS_FALLBACK" in receipt.error


def test_opt_in_process_backend_actually_runs(monkeypatch):
    import nexara_prime.sandbox_v2 as sb

    monkeypatch.setattr(sb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sb.shutil, "which", lambda _name: None)
    backend = select_sandbox_backend("/tmp", allow_process_fallback=True)
    assert isinstance(backend, ProcessConstrainedBackend)
    assert backend.probe_capability().sandbox_mechanism == "process_restricted"
    receipt = backend.execute(SandboxInvocation(
        argv=["python3", "-c", "print('t2-ok')"], cwd="/tmp", timeout=30, max_output_bytes=4096,
    ))
    assert receipt.exit_code == 0, receipt.error
    assert "t2-ok" in receipt.stdout
    assert receipt.sandbox_mechanism == "process_restricted"
