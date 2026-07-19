"""Production sandbox — macOS sandbox-exec, workspace jail, test backend.
P0-1: No silent fallback. OS_SANDBOX_CAPABLE vs OS_SANDBOX_ENFORCED vs FULL_OS_ISOLATION_ACCEPTED."""
from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .models import new_id, now_iso


# ── Capability flags ──

OS_SANDBOX_CAPABLE = "OS_SANDBOX_CAPABLE"
OS_SANDBOX_ENFORCED = "OS_SANDBOX_ENFORCED"
WORKSPACE_JAIL_ENFORCED = "WORKSPACE_JAIL_ENFORCED"
FULL_OS_ISOLATION_ACCEPTED = "FULL_OS_ISOLATION_ACCEPTED"


@dataclass
class SandboxCapability:
    flags: list[str] = field(default_factory=list)
    sandbox_mechanism: str = "none"
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
    escape_tests_passed: int = 0


@dataclass
class SandboxInvocation:
    invocation_id: str = field(default_factory=lambda: new_id("sbx"))
    command: str = ""
    argv: list[str] = field(default_factory=list)
    cwd: str = ""
    env: dict = field(default_factory=dict)
    timeout: float = 30.0
    max_output_bytes: int = 100_000
    created_at: str = field(default_factory=now_iso)
    workspace_root: str = ""


@dataclass
class SandboxReceipt:
    invocation_id: str = ""
    exit_code: int = -99
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    was_killed: bool = False
    duration_ms: float = 0.0
    error: str = ""
    sandbox_profile_hash: str = ""
    code_hash: str = ""
    files_touched: list[str] = field(default_factory=list)
    network_attempts: int = 0
    policy_decisions: list[dict] = field(default_factory=list)
    resource_usage: dict = field(default_factory=dict)


class SandboxBackend(ABC):
    @abstractmethod
    def probe_capability(self) -> SandboxCapability: ...
    @abstractmethod
    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt: ...


# ── macOS sandbox-exec profile ──

def _build_sandbox_profile(workspace_root: str, tmpdir: str = "/tmp",
                            allow_network: bool = False,
                            allowed_dirs: list[str] | None = None,
                            allowed_executables: list[str] | None = None) -> str:
    """Build a sandbox-exec .sb profile that denies everything except explicit allows."""
    ws = os.path.realpath(workspace_root)
    td = os.path.realpath(tmpdir)
    dirs = [
        ws, td,
        "/usr", "/bin", "/sbin", "/System", "/Library",
        "/private/etc", "/private/var/db", "/private/var/folders", "/private/var/tmp", "/private/tmp", "/dev",
    ] + (allowed_dirs or [])
    deduped_dirs = []
    for directory in dirs:
        real = os.path.realpath(directory)
        if real and real not in deduped_dirs:
            deduped_dirs.append(real)
    dirs = deduped_dirs
    read_dirs = " ".join(f'(subpath "{d}")' for d in dirs)
    write_dirs = " ".join(f'(subpath "{d}")' for d in [ws, td])
    home = os.path.realpath(os.path.expanduser("~"))
    executable_paths = []
    for executable in allowed_executables or []:
        real = os.path.realpath(executable)
        if real and real not in executable_paths:
            executable_paths.append(real)
        # Homebrew/Framework Python (e.g. Python.framework or Python3.framework)
        # launches its embedded Python.app.
        if re.search(r"/Python\d*\.framework/Versions/", real):
            version_root = Path(real).parent.parent
            app_executable = version_root / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
            app_real = os.path.realpath(app_executable)
            if app_real not in executable_paths:
                executable_paths.append(app_real)
    executable_paths.extend([
        "/usr/bin/python3", "/usr/bin/python3.12", "/bin/bash", "/bin/sh", "/usr/bin/env",
    ])
    executable_paths = list(dict.fromkeys(executable_paths))
    exec_rules = "\n       ".join(f'(literal "{path}")' for path in executable_paths)

    profile = f"""\
(version 1)
(deny default)
(allow file-read*)
(deny file-read* (subpath "{home}"))
(allow file-read* {read_dirs}
       (subpath "/usr/lib")
       (subpath "/System/Library")
       (subpath "/Library/Frameworks")
       (subpath "/opt/homebrew")
       (subpath "/private/var/db/dyld"))
(allow file-write* {write_dirs})
(allow file-read-metadata)
(allow process-exec
       {exec_rules})
(allow process-fork)
(allow signal)
(allow sysctl-read)
(allow mach-lookup
       (global-name "com.apple.bsd.dirhelper")
       (global-name "com.apple.system.notification_center"))
"""
    if allow_network:
        profile += "(allow network-outbound)\n"
    else:
        profile += "(deny network-outbound)\n"

    return profile


class MacOSSandboxBackend(SandboxBackend):
    """macOS sandbox using sandbox-exec with .sb profile. No silent fallback."""

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = workspace_root or os.getcwd()
        self._sandbox_exec = shutil.which("sandbox-exec")
        self._enforced: bool = False
        self._escape_tests: int = 0

    def probe_capability(self) -> SandboxCapability:
        cap = SandboxCapability()
        if platform.system() != "Darwin":
            cap.sandbox_mechanism = "workspace_jail"
            cap.flags = [WORKSPACE_JAIL_ENFORCED]
            return cap

        if self._sandbox_exec:
            cap.flags.append(OS_SANDBOX_CAPABLE)
            if self._enforced:
                cap.flags.append(OS_SANDBOX_ENFORCED)
            if self._escape_tests >= 10:
                cap.flags.append(FULL_OS_ISOLATION_ACCEPTED)
            cap.sandbox_mechanism = "macos_sandbox"
            cap.verified_at = now_iso()
            cap.escape_tests_passed = self._escape_tests
        else:
            cap.sandbox_mechanism = "workspace_jail"
            cap.flags = [WORKSPACE_JAIL_ENFORCED]
        return cap

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        ws = invocation.workspace_root or self.workspace_root
        if not self._sandbox_exec:
            return SandboxReceipt(
                invocation_id=invocation.invocation_id,
                error="sandbox-exec not available — BLOCKED, no fallback to plain execution",
            )

        cmd = invocation.argv if invocation.argv else shlex.split(invocation.command)
        if not cmd:
            return SandboxReceipt(invocation_id=invocation.invocation_id, error="command_must_not_be_empty")
        executable = cmd[0] if os.path.isabs(cmd[0]) else shutil.which(cmd[0])
        if executable:
            cmd[0] = os.path.realpath(executable)
        allowed_dirs = invocation.env.get("NEXARA_ALLOWED_DIRS", "").split(":") if invocation.env.get("NEXARA_ALLOWED_DIRS") else None
        profile = _build_sandbox_profile(
            ws,
            tmpdir=tempfile.gettempdir(),
            allow_network=False,
            allowed_dirs=allowed_dirs,
            allowed_executables=[cmd[0]],
        )

        # Write profile to temp file
        fd, profile_path = tempfile.mkstemp(suffix=".sb", prefix="nexara_sandbox_")
        try:
            os.write(fd, profile.encode())
            os.close(fd)

            started = time.time()
            full_cmd = [self._sandbox_exec, "-f", profile_path, "--"] + cmd

            env = {}
            safe_keys = {"PATH", "HOME", "TMPDIR", "LANG"}
            for k in safe_keys:
                if k in (invocation.env or {}):
                    env[k] = invocation.env[k]
            env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

            self._enforced = True
            try:
                proc = subprocess.Popen(
                    full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=ws, env=env, text=True, shell=False,
                    preexec_fn=os.setsid,
                )
                try:
                    out, err_out = proc.communicate(timeout=invocation.timeout)
                    elapsed = (time.time() - started) * 1000
                    stdout = (out or "")[:invocation.max_output_bytes]
                    stderr = (err_out or "")[:invocation.max_output_bytes]
                    # Detect posix_spawn failures in sandbox-exec (macOS hardened runtime)
                    if proc.returncode != 0 and "posix_spawn" in (err_out or ""):
                        return SandboxReceipt(
                            invocation_id=invocation.invocation_id,
                            exit_code=proc.returncode,
                            error="sandbox_posix_spawn_failure",
                            duration_ms=elapsed,
                        )
                    return SandboxReceipt(
                        invocation_id=invocation.invocation_id,
                        exit_code=proc.returncode,
                        stdout=stdout, stderr=stderr, duration_ms=elapsed,
                        sandbox_profile_hash=_hash_str(profile),
                    )
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        proc.kill()
                    proc.wait()
                    if proc.stdout:
                        proc.stdout.close()
                    if proc.stderr:
                        proc.stderr.close()
                    return SandboxReceipt(
                        invocation_id=invocation.invocation_id,
                        timed_out=True, was_killed=True,
                        duration_ms=(time.time() - started) * 1000,
                        error="timeout", sandbox_profile_hash=_hash_str(profile),
                    )
            except Exception as exc:
                return SandboxReceipt(
                    invocation_id=invocation.invocation_id,
                    error=str(exc), duration_ms=(time.time() - started) * 1000,
                )
        finally:
            try:
                os.unlink(profile_path)
            except OSError:
                pass

    def run_escape_test(self, test_name: str, argv: list[str],
                         expected_result: str = "blocked") -> bool:
        """Run a single escape test. Returns True if sandbox behaved as expected."""
        inv = SandboxInvocation(argv=argv, timeout=5.0, workspace_root=self.workspace_root)
        receipt = self.execute(inv)
        if expected_result == "blocked":
            passed = receipt.exit_code != 0 or "denied" in receipt.stderr.lower() or "operation not permitted" in receipt.stderr.lower()
        elif expected_result == "allow":
            passed = receipt.exit_code == 0
        else:
            passed = False
        if passed:
            self._escape_tests += 1
        return passed


class ProcessConstrainedBackend(SandboxBackend):
    def probe_capability(self) -> SandboxCapability:
        return SandboxCapability(flags=[WORKSPACE_JAIL_ENFORCED], sandbox_mechanism="workspace_jail")

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        return _workspace_jail_execute(invocation)


class TestSandboxBackend(SandboxBackend):
    def __init__(self, workspace_root: str = "/tmp/nexara-test-sandbox"):
        self.workspace_root = workspace_root
        os.makedirs(workspace_root, exist_ok=True)

    def probe_capability(self) -> SandboxCapability:
        return SandboxCapability(flags=[], sandbox_mechanism="test", allow_network=True)

    def execute(self, invocation: SandboxInvocation) -> SandboxReceipt:
        cwd = invocation.cwd or self.workspace_root
        started = time.time()
        cmd = invocation.argv if invocation.argv else shlex.split(invocation.command)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                                    timeout=invocation.timeout, shell=False)
            elapsed = (time.time() - started) * 1000
            return SandboxReceipt(
                invocation_id=invocation.invocation_id, exit_code=result.returncode,
                stdout=result.stdout[:invocation.max_output_bytes] if result.stdout else "",
                stderr=result.stderr[:invocation.max_output_bytes] if result.stderr else "",
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            return SandboxReceipt(invocation_id=invocation.invocation_id, timed_out=True, error="timeout")
        except Exception as exc:
            return SandboxReceipt(invocation_id=invocation.invocation_id, error=str(exc))


# ── Shared helpers ──

def _hash_str(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()[:16]


_FORBIDDEN_COMMANDS = {"rm", "shutdown", "reboot", "mkfs", "dd", "mount", "umount", "chown", "chmod", "sudo", "su", "passwd", "killall"}
_PATH_TRAVERSAL_PATTERNS = ["../", "..\\"]


def _validate_path(path_str: str, workspace_root: str) -> tuple[bool, str]:
    if not path_str:
        return True, ""
    import urllib.parse
    decoded = urllib.parse.unquote(path_str)
    if "\0" in path_str or "\x00" in path_str:
        return False, "null byte in path"
    for pat in _PATH_TRAVERSAL_PATTERNS:
        if pat in decoded:
            return False, f"path traversal: {pat}"
    try:
        resolved = os.path.realpath(os.path.join(workspace_root, decoded))
        workspace_real = os.path.realpath(workspace_root)
        if not resolved.startswith(workspace_real + os.sep) and resolved != workspace_real:
            return False, f"path escape: {path_str}"
    except Exception:
        return False, "path resolution failed"
    return True, ""


def _sanitize_argv(argv: list[str]) -> tuple[list[str], str]:
    dangerous = {"|", ";", "&", "`", "$(", "${", "&&", "||", ">", "<"}
    for i, arg in enumerate(argv):
        for d in dangerous:
            if d in arg:
                return [], f"shell metacharacter '{d}' in arg[{i}]"
    return argv, ""


def _validate_command(command: str, argv: list[str]) -> tuple[bool, str]:
    if not argv:
        return False, "no command"
    basename = os.path.basename(argv[0])
    if basename in _FORBIDDEN_COMMANDS:
        return False, f"forbidden: {basename}"
    return True, ""


def _workspace_jail_execute(invocation: SandboxInvocation) -> SandboxReceipt:
    started = time.time()
    cmd = invocation.argv if invocation.argv else shlex.split(invocation.command)
    cwd = invocation.cwd or os.getcwd()

    sanitized, err = _sanitize_argv(cmd)
    if err:
        return SandboxReceipt(invocation_id=invocation.invocation_id, error=err)
    ok, reason = _validate_command(invocation.command, sanitized)
    if not ok:
        return SandboxReceipt(invocation_id=invocation.invocation_id, error=reason)

    env = {}
    safe_env = {"PATH", "HOME", "USER", "TMPDIR", "LANG", "PYTHONPATH"}
    if invocation.env:
        for k in safe_env:
            if k in invocation.env:
                env[k] = invocation.env[k]
    else:
        for k in safe_env:
            if k in os.environ:
                env[k] = os.environ[k]
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    try:
        proc = subprocess.Popen(sanitized, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 cwd=cwd, env=env, text=True, shell=False, preexec_fn=os.setsid)
        try:
            out, err_out = proc.communicate(timeout=invocation.timeout)
            elapsed = (time.time() - started) * 1000
            return SandboxReceipt(
                invocation_id=invocation.invocation_id, exit_code=proc.returncode,
                stdout=(out or "")[:invocation.max_output_bytes],
                stderr=(err_out or "")[:invocation.max_output_bytes], duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.wait()
            return SandboxReceipt(invocation_id=invocation.invocation_id, timed_out=True,
                                   was_killed=True, error="timeout")
    except Exception as exc:
        return SandboxReceipt(invocation_id=invocation.invocation_id, error=str(exc))
