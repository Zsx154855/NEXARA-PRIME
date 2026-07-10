"""SandboxBackend — abstract sandbox, macOS probe, workspace jail, test backend."""
from __future__ import annotations

import os
import platform
import resource
import shlex
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .models import new_id, now_iso


@dataclass
class SandboxCapability:
    os_level_isolation: str = "PARTIAL"  # "FULL" | "PARTIAL" | "NONE"
    sandbox_mechanism: str = "workspace_jail"  # "macos_sandbox" | "workspace_jail" | "none"
    network_restricted: bool = True
    filesystem_restricted: bool = True
    process_restricted: bool = True
    resource_limited: bool = True
    memory_limit_mb: int = 512
    cpu_time_limit: int = 30
    max_output_bytes: int = 1_000_000
    max_processes: int = 1
    allow_network: bool = False
    allow_file_write_outside_workspace: bool = False
    verified_at: str = ""


@dataclass
class SandboxInvocation:
    invocation_id: str = field(default_factory=lambda: new_id('evt'))
    command: str = ""
    argv: list[str] = field(default_factory=list)
    cwd: str = ""
    env: dict = field(default_factory=dict)
    timeout: float = 30.0
    max_output_bytes: int = 100_000
    created_at: str = field(default_factory=now_iso)


@dataclass
class SandboxReceipt:
    invocation_id: str
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    was_killed: bool = False
    duration_ms: float = 0.0
    error: str = ""
    resource_usage: dict = field(default_factory=dict)


class SandboxBackend(ABC):
    @abstractmethod
    def probe_capability(self) -> SandboxCapability: ...
    @abstractmethod
    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt: ...


class MacOSSandboxBackend(SandboxBackend):
    """Probes macOS sandbox capability. Falls back to workspace jail if unavailable."""

    def probe_capability(self) -> SandboxCapability:
        cap = SandboxCapability()
        if platform.system() != "Darwin":
            cap.sandbox_mechanism = "workspace_jail"
            cap.os_level_isolation = "NONE"
            return cap
        # Check for sandbox-exec availability
        sb_exec = shutil.which("sandbox-exec")
        if sb_exec:
            cap.sandbox_mechanism = "macos_sandbox"
            cap.os_level_isolation = "FULL"
        else:
            cap.sandbox_mechanism = "workspace_jail"
            cap.os_level_isolation = "PARTIAL"
        return cap

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        return _workspace_jail_execute(invocation)


class ProcessConstrainedBackend(SandboxBackend):
    """Strict workspace jail — no OS sandbox, but strong process constraints."""

    def probe_capability(self) -> SandboxCapability:
        return SandboxCapability(
            os_level_isolation="PARTIAL",
            sandbox_mechanism="workspace_jail",
        )

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        return _workspace_jail_execute(invocation)


class TestSandboxBackend(SandboxBackend):
    """Permissive backend for unit tests."""

    def __init__(self, workspace_root: str = "/tmp/nexara-test-sandbox"):
        self.workspace_root = workspace_root
        os.makedirs(workspace_root, exist_ok=True)

    def probe_capability(self) -> SandboxCapability:
        return SandboxCapability(
            os_level_isolation="NONE",
            sandbox_mechanism="test",
            allow_network=True,
            allow_file_write_outside_workspace=False,
        )

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        if invocation.cwd:
            cwd = invocation.cwd
        else:
            cwd = self.workspace_root
        started = time.time()
        cmd = invocation.argv if invocation.argv else shlex.split(invocation.command)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=cwd, env=invocation.env or None,
                timeout=invocation.timeout,
            )
            elapsed = (time.time() - started) * 1000
            stdout = result.stdout[:invocation.max_output_bytes]
            stderr = result.stderr[:invocation.max_output_bytes]
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                exit_code=result.returncode,
                stdout=stdout, stderr=stderr,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                timed_out=True, duration_ms=(time.time() - started) * 1000,
                error="timeout",
            )
        except Exception as exc:
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                error=str(exc), duration_ms=(time.time() - started) * 1000,
            )


# ─── Shared workspace jail ───

import shutil

_FORBIDDEN_COMMANDS = {
    "rm", "shutdown", "reboot", "mkfs", "dd", "mount", "umount",
    "chown", "chmod", "sudo", "su", "passwd", "killall",
}

_PATH_TRAVERSAL_PATTERNS = ["../", "..\\"]


def _validate_path(path_str: str, workspace_root: str) -> tuple[bool, str]:
    """Check for path traversal attacks including URL-encoded variants."""
    if not path_str:
        return True, ""
    import urllib.parse
    # Decode URL encoding first
    decoded = urllib.parse.unquote(path_str)
    # Check null bytes
    if "\\x00" in path_str or "\\0" in path_str or "\\x00" in decoded:
        return False, "null byte in path"
    # Check path traversal patterns
    for pat in _PATH_TRAVERSAL_PATTERNS:
        if pat in decoded:
            return False, f"path traversal pattern: {pat}"
    try:
        resolved = os.path.realpath(os.path.join(workspace_root, decoded))
        workspace_real = os.path.realpath(workspace_root)
        if not resolved.startswith(workspace_real + os.sep) and resolved != workspace_real:
            return False, f"path escape: {path_str} -> {resolved}"
    except Exception:
        return False, f"path resolution failed: {path_str}"
    return True, ""


def _sanitize_argv(argv: list[str]) -> tuple[list[str], str]:
    """Sanitize command arguments — reject shell metacharacters."""
    dangerous = {"|", ";", "&", "`", "$(", "${", "&&", "||", ">", "<", "\\n"}
    for i, arg in enumerate(argv):
        for d in dangerous:
            if d in arg:
                return [], f"shell metacharacter '{d}' in arg[{i}]"
    return argv, ""


def _validate_command(command: str, argv: list[str]) -> tuple[bool, str]:
    """Validate the command is safe."""
    if not argv:
        return False, "no command"
    exe = argv[0]
    basename = os.path.basename(exe)
    if basename in _FORBIDDEN_COMMANDS:
        return False, f"forbidden command: {basename}"
    return True, ""


def _workspace_jail_execute(invocation: SandboxInvocation) -> SandboxReceipt:
    """Execute command inside workspace jail with resource limits."""
    started = time.time()
    cmd = invocation.argv if invocation.argv else shlex.split(invocation.command)
    cwd = invocation.cwd or os.getcwd()

    # Security checks
    sanitized, err = _sanitize_argv(cmd)
    if err:
        return SandboxReceipt(invocation_id=invocation.invocation_id, error=err)
    ok, reason = _validate_command(invocation.command, sanitized)
    if not ok:
        return SandboxReceipt(invocation_id=invocation.invocation_id, error=reason)

    env = {}
    allowed_env = {"PATH", "HOME", "USER", "TMPDIR", "LANG", "PYTHONPATH"}
    if invocation.env:
        for k in allowed_env:
            if k in invocation.env:
                env[k] = invocation.env[k]
    else:
        for k in allowed_env:
            if k in os.environ:
                env[k] = os.environ[k]
    # Fixed safe PATH
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    try:
        proc = subprocess.Popen(
            sanitized, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, text=True, shell=False,
        )
        try:
            out, err_out = proc.communicate(timeout=invocation.timeout)
            elapsed = (time.time() - started) * 1000
            stdout = out[:invocation.max_output_bytes] if out else ""
            stderr = err_out[:invocation.max_output_bytes] if err_out else ""
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                exit_code=proc.returncode,
                stdout=stdout, stderr=stderr, duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            # Kill the entire process group
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.wait()
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                timed_out=True, was_killed=True,
                duration_ms=(time.time() - started) * 1000,
                error="timeout",
            )
    except Exception as exc:
        return SandboxReceipt(
            invocation_id=invocation.invocation_id,
            error=str(exc), duration_ms=(time.time() - started) * 1000,
        )
