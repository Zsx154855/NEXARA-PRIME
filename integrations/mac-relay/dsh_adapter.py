"""Real DSH adapter: fixed binary, fixed argv template, isolated env, stdin-only task."""
from __future__ import annotations

import json
import os
import subprocess

from p3_dsh import DEADLINE_SLACK_SECONDS, ProcessAdapter

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DSH_BINARY = shutil.which("dsh") or "/opt/homebrew/bin/dsh"
PATCH_PATH = str(HERE / "dsh-local-route.patch.yml")
MODEL = "nexara-local-qwen3"
ROUTE_ENDPOINT = "http://127.0.0.1:11434/v1"
KEY_ENV = "NEXARA_LOCAL_MODEL_KEY"


class DshAdapter:
    """argv is fixed; the task text only ever travels on stdin."""

    def __init__(self, dsh=DSH_BINARY, patch=PATCH_PATH, model=MODEL):
        self.argv = [dsh, "--profile", "headless", "--patch", patch, "--json", "-"]
        self.model = model

    def _environment(self):
        env = {name: os.environ[name] for name in ("HOME", "PATH", "TMPDIR", "LANG") if name in os.environ}
        env.setdefault("PATH", "/usr/bin:/bin:/opt/homebrew/bin")
        env[KEY_ENV] = "local"
        for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            env.pop(name, None)
        return env

    def __call__(self, instruction, timeout, workspace):
        process = subprocess.Popen(self.argv, cwd=workspace, env=self._environment(),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True, text=True)
        try:
            out, err = process.communicate(instruction, timeout=timeout)
        except subprocess.TimeoutExpired:
            ProcessAdapter.terminate(process)
            raise
        return {"exit_code": process.returncode, "stdout": out.encode(), "stderr": err.encode(),
                "metering": self._metering(out)}

    @staticmethod
    def _metering(stream):
        calls = 0
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and isinstance(event.get("usage"), dict):
                calls += 1
        if calls == 0:
            return {"model_calls": "unknown", "source": "dsh-json-events"}
        return {"model_calls": calls, "source": "dsh-json-events"}
