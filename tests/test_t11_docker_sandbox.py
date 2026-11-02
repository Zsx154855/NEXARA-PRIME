"""T11: a Docker backend so an external user on Linux can run real work.

Docker is optional at test time: the argv/flags are unit-tested, and the
end-to-end run is skipped (not silently passed) when Docker is unavailable.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from nexara_prime.sandbox_v2 import DockerSandboxBackend, SandboxInvocation


def test_argv_is_hardened(monkeypatch):
    """Network off, read-only root, memory/pids caps, workspace mounted rw."""
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend = DockerSandboxBackend("/tmp/ws", image="nexara-sandbox:test")
    # Pretend the CLI and daemon exist: this test is about argv construction.
    backend._docker = "/usr/local/bin/docker"
    backend._usable = True
    receipt = backend.execute(SandboxInvocation(
        argv=["python3", "-c", "print('hi')"], cwd="/tmp/ws", timeout=30, max_output_bytes=4096))

    assert receipt.exit_code == 0
    argv = captured["argv"]
    joined = " ".join(argv)
    assert "--network" in joined and "none" in joined
    assert "--read-only" in joined
    assert "--pids-limit" in joined
    assert "-v" in joined and "/tmp/ws:/workspace" in joined
    assert receipt.sandbox_mechanism == "docker"


def test_probe_reports_unavailable_without_docker(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    backend = DockerSandboxBackend("/tmp/ws")
    assert backend.probe_capability().sandbox_mechanism == "none"
    receipt = backend.execute(SandboxInvocation(argv=["echo", "x"], cwd="/tmp/ws", timeout=5))
    assert receipt.error and "docker" in receipt.error.lower()


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_real_container_has_no_network(tmp_path):
    backend = DockerSandboxBackend(str(tmp_path))
    if backend.probe_capability().sandbox_mechanism != "docker":
        pytest.skip("docker daemon not reachable")
    receipt = backend.execute(SandboxInvocation(
        argv=["sh", "-lc", "python3 -c \"import socket;socket.create_connection(('1.1.1.1',80),2)\""],
        cwd=str(tmp_path), timeout=60))
    assert receipt.exit_code != 0
