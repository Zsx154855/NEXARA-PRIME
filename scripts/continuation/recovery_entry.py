#!/usr/bin/env python3
"""Recovery entry: run the checkpoint's next task once via the existing dsh CLI.

This is NOT a scheduler and installs nothing. It is a one-shot adapter:
  checkpoint JSON {"next_task": {"id": "...", "prompt": "..."}}
  -> `dsh headless "<prompt>"`
Dispatch is guarded by a per-task lock so repeated recovery/retry attempts do
not silently duplicate side effects. Use --execute to actually spawn dsh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_next_task(checkpoint_path: Path) -> dict[str, str]:
    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    task = data.get("next_task")
    if not isinstance(task, dict):
        raise ValueError("checkpoint_missing_next_task")
    task_id = str(task.get("id") or "")
    prompt = str(task.get("prompt") or "")
    if not task_id or not prompt:
        raise ValueError("next_task_requires_id_and_prompt")
    return {"id": task_id, "prompt": prompt}


def task_digest(task: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(task, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _write_lock(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def plan_dispatch(task: dict[str, str], dsh_bin: str) -> list[str]:
    return [dsh_bin, "headless", task["prompt"]]


def dispatch(
    task: dict[str, str],
    state_dir: Path,
    *,
    dsh_bin: str = "dsh",
    execute: bool = False,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    digest = task_digest(task)
    lock_path = state_dir / f"task-{task['id']}.lock"
    if lock_path.exists():
        existing = json.loads(lock_path.read_text(encoding="utf-8"))
        if existing.get("digest") == digest and existing.get("state") == "done":
            return {"status": "already_completed", "task_id": task["id"], "lock": str(lock_path)}
    command = plan_dispatch(task, dsh_bin)
    result: dict[str, Any] = {
        "status": "planned" if not execute else "unknown",
        "task_id": task["id"],
        "digest": digest,
        "command": command,
    }
    if not execute:
        return result
    _write_lock(lock_path, {**result, "state": "running"})
    try:
        proc = subprocess.run(command, timeout=timeout_seconds)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    result["returncode"] = returncode
    result["status"] = "done" if returncode == 0 else "failed"
    _write_lock(lock_path, {**result, "state": result["status"]})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(".nexara/continuation"))
    parser.add_argument("--dsh-bin", default="dsh")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        task = load_next_task(args.checkpoint)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"recovery_entry_error: {exc}", file=sys.stderr)
        return 2
    result = dispatch(
        task, args.state_dir, dsh_bin=args.dsh_bin, execute=args.execute
    )
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result["command"])
    return 0 if result["status"] in {"planned", "done", "already_completed"} else 1


if __name__ == "__main__":
    sys.exit(main())
