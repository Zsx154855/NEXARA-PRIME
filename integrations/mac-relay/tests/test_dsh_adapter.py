"""Unit contracts for the real DSH adapter. No network, no model call."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import dsh_adapter
from dsh_adapter import DshAdapter


class FakeProcess:
    def __init__(self, stdout="", stderr="", code=0, timeout=False):
        self.stdout_text, self.stderr_text, self.returncode = stdout, stderr, code
        self._timeout = timeout
        self.pid = 999999
        self.stdin_args = None
        self.killed = False

    def communicate(self, instruction=None, timeout=None):
        self.stdin_args = instruction
        if self._timeout:
            raise subprocess.TimeoutExpired(cmd="dsh", timeout=timeout)
        return self.stdout_text, self.stderr_text

    def poll(self):
        return self.returncode


def install(monkeypatch, process, captured):
    def fake_popen(argv, **kwargs):
        captured.append((argv, kwargs))
        return process

    monkeypatch.setattr(dsh_adapter.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dsh_adapter.ProcessAdapter, "terminate", staticmethod(lambda p: p.killed or True))


def test_argv_is_fixed_and_instruction_travels_on_stdin(monkeypatch):
    captured, seen = [], FakeProcess(stdout='{"usage":{"total_tokens":5}}\n')
    install(monkeypatch, seen, captured)
    DshAdapter()("rm -rf / --no-preserve-root", 20, "/private/tmp")
    argv, kwargs = captured[0]
    assert argv[:4] == ["/opt/homebrew/bin/dsh", "--profile", "headless", "--patch"]
    assert argv[-2:] == ["--json", "-"]
    assert "rm -rf" not in " ".join(argv)
    assert seen.stdin_args == "rm -rf / --no-preserve-root"
    assert kwargs["start_new_session"] is True


def test_environment_is_whitelisted_and_billable_keys_dropped(monkeypatch):
    captured, seen = [], FakeProcess()
    install(monkeypatch, seen, captured)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-should-not-leak")
    DshAdapter()("hi", 20, "/private/tmp")
    env = captured[0][1]["env"]
    assert "OPENAI_API_KEY" not in env and "DEEPSEEK_API_KEY" not in env
    assert env[dsh_adapter.KEY_ENV] == "local"
    assert set(env) <= {"HOME", "PATH", "TMPDIR", "LANG", dsh_adapter.KEY_ENV}


def test_metering_counts_real_usage_events(monkeypatch):
    stream = json.dumps({"type": "a", "usage": {"total_tokens": 3}}) + chr(10) + json.dumps({"type": "b"}) + chr(10)
    captured = []
    install(monkeypatch, FakeProcess(stdout=stream), captured)
    outcome = DshAdapter()("hi", 20, "/private/tmp")
    assert outcome["metering"] == {"model_calls": 1, "source": "dsh-json-events"}


def test_metering_is_unknown_without_usage_events(monkeypatch):
    install(monkeypatch, FakeProcess(stdout="not json"), [])
    outcome = DshAdapter()("hi", 20, "/private/tmp")
    assert outcome["metering"]["model_calls"] == "unknown"


def test_timeout_routes_through_the_kill_path(monkeypatch):
    captured, seen = [], FakeProcess(timeout=True)
    install(monkeypatch, seen, captured)
    with pytest.raises(subprocess.TimeoutExpired):
        DshAdapter()("hi", 20, "/private/tmp")
