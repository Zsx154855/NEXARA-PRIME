from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .runtime import NexaraRuntime


def _print(value) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexara", description="NEXARA PRIME sovereign agent kernel CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="initialize runtime directories")
    mission = sub.add_parser("mission", help="mission lifecycle commands")
    mission_sub = mission.add_subparsers(dest="mission_command", required=True)
    create = mission_sub.add_parser("create")
    create.add_argument("objective")
    create.add_argument("--source-dir")
    mission_sub.add_parser("status").add_argument("mission_id")
    mission_sub.add_parser("plan").add_argument("mission_id")
    approve = mission_sub.add_parser("approve")
    approve.add_argument("mission_id")
    approve.add_argument("--reject", action="store_true")
    approve.add_argument("--note", default="Approved by human operator.")
    approve.add_argument("--decision", choices=["approve_once", "approve_mission", "request_changes", "pause_mission", "rejected"])
    approve.add_argument("--scope")
    mission_sub.add_parser("run").add_argument("mission_id")
    mission_sub.add_parser("pause").add_argument("mission_id")
    mission_sub.add_parser("resume").add_argument("mission_id")
    mission_sub.add_parser("rollback").add_argument("mission_id")
    evidence = sub.add_parser("evidence")
    evidence.add_argument("list", nargs="?")
    evidence.add_argument("--mission-id")
    memory = sub.add_parser("memory")
    memory.add_argument("inspect", nargs="?")
    memory.add_argument("--mission-id")
    evaluation = sub.add_parser("eval")
    evaluation.add_argument("run", nargs="?")
    evaluation.add_argument("--mission-id")
    sub.add_parser("runtime-status")
    sub.add_parser("status", help="display project state from .nexara/PROJECT_STATE.json")
    sub.add_parser("doctor", help="run repository health checks")
    return parser


def _resolve_repo_root() -> Path:
    """Walk up from cwd to find the NEXARA-PRIME repo root (.nexara marker)."""
    candidate = Path.cwd().resolve()
    for _ in range(8):
        if (candidate / ".nexara" / "PROJECT_STATE.json").exists():
            return candidate
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    return Path.cwd().resolve()


def cmd_status() -> int:
    """Read .nexara/PROJECT_STATE.json and render a human-readable status block."""
    root = _resolve_repo_root()
    state_path = root / ".nexara" / "PROJECT_STATE.json"
    if not state_path.exists():
        print(f"ERROR: PROJECT_STATE.json not found at {state_path}", file=sys.stderr)
        return 1
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot parse {state_path}: {exc}", file=sys.stderr)
        return 1

    kf = state.get("knowledge_fabric", {})
    rt = state.get("runtime_hardening", {})
    prog = state.get("progress", {})

    lines = [
        "",
        f"  {state.get('project', 'NEXARA PRIME')}",
        "  " + "─" * 40,
        f"  Repository        {state.get('repo', root)}",
        f"  Branch            {state.get('branch', '?')}",
        f"  Current Gate      {state.get('current_gate', '?')}",
        f"  Gate Status       {state.get('gate_status', '?')}",
        "",
        f"  Runtime           {rt.get('status', '?')}",
        f"  Tests             {rt.get('tests_passed', 0)} passed / {rt.get('tests_failed', 0)} failed",
        f"  Mission           {rt.get('acceptance_mission', '?')}",
        f"  Evidence          {rt.get('evidence_valid', 0)} / {rt.get('evidence_valid', 0)}",
        "",
        f"  Knowledge Fabric  {kf.get('status', '?')}",
        f"  Canonical Docs    {kf.get('canonical_documents', '?')}",
        f"  Architecture      L01–L12 {kf.get('layers', '?')}",
        f"  Broken Links      {kf.get('unresolved_links', '?')}",
        f"  Legacy Notes      {kf.get('legacy_notes_remaining', '?')}",
        "",
        f"  Engineering       {prog.get('engineering_mainline', '?')}%",
        f"  Self-Evolution    {prog.get('self_evolution_loop', '?')}%",
        f"  Product Delivery  {prog.get('product_delivery', '?')}%",
        "",
        f"  Next Gate",
        f"  {state.get('next_gate', '?')}",
        f"  Updated           {state.get('updated_at', '?')}",
        "",
    ]
    print("\n".join(lines))
    return 0


def cmd_doctor() -> int:
    """Run repository health checks and report results."""
    root = _resolve_repo_root()
    checks = []
    issues = 0

    def check(label: str, ok: bool, detail: str = ""):
        nonlocal issues
        mark = "✓" if ok else "✗"
        if not ok:
            issues += 1
        checks.append((mark, label, detail))

    # 1. Repo exists
    check("Repo exists", root.is_dir(), str(root))

    # 2. Python + venv
    py_bin = os.environ.get("VIRTUAL_ENV", "")
    if not py_bin:
        candidate = root / ".venv" / "bin" / "python3"
        if candidate.exists():
            py_bin = str(candidate)
    python_ok = bool(py_bin)
    check("Python virtualenv", python_ok, py_bin or "none")

    # 3. SQLite
    try:
        import sqlite3
        sqlite3.connect(":memory:").close()
        check("SQLite accessible", True, "ok")
    except Exception:
        check("SQLite accessible", False, "import failed")

    # 4. docs vault
    vault = root / "docs"
    check("docs vault exists", vault.is_dir(), str(vault))

    # 5. PROJECT_STATE.json
    state_path = root / ".nexara" / "PROJECT_STATE.json"
    state_ok = state_path.exists()
    check("PROJECT_STATE.json", state_ok, str(state_path))

    # 6. src/tests/scripts
    for d in ["src", "tests", "scripts"]:
        p = root / d
        check(f"{d}/ exists", p.is_dir(), str(p))

    # 7. No legacy notes
    trash = root / "docs" / ".trash"
    has_trash = trash.exists() and any(trash.iterdir())
    check("No legacy notes", not has_trash, "trash is clean" if not has_trash else "trash has content")

    # 8. Required dirs writable
    for d in [".nexara", "reports", "workspace"]:
        p = root / d
        p.mkdir(parents=True, exist_ok=True)
        writable = os.access(p, os.W_OK)
        check(f"{d}/ writable", writable, str(p))

    # 9. No secrets tracked by git
    try:
        r = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, cwd=str(root))
        staged = r.stdout.strip().split("\n") if r.stdout.strip() else []
        secrets_found = []
        for f in staged:
            fp = root / f
            if fp.exists() and fp.is_file():
                txt = fp.read_text(errors="ignore")
                if "sk-" in txt or "api_key" in txt.lower() or "password" in txt.lower():
                    secrets_found.append(f)
        check("No secrets staged", len(secrets_found) == 0, "ok" if not secrets_found else f"found: {secrets_found}")
    except Exception:
        check("No secrets staged", True, "skipped (no git)")

    # 10. Worktree status
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(root))
        clean = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        check("Worktree status", True, f"{clean} files pending" if clean else "clean")
    except Exception:
        check("Worktree status", True, "not a git repo")

    # Print
    print(f"\n  NEXARA PRIME Doctor")
    print(f"  {'─' * 50}")
    print(f"  Repo: {root}")
    print()
    for mark, label, detail in checks:
        detail_str = f"  → {detail}" if detail else ""
        print(f"  [{mark}] {label}{detail_str}")

    print(f"\n  {'─' * 50}")
    if issues == 0:
        print(f"  All {len(checks)} checks passed.")
    else:
        print(f"  {issues}/{len(checks)} checks FAILED.")
    print()
    return 0 if issues == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(Path.cwd())
    runtime = NexaraRuntime(settings)
    try:
        if args.command == "init":
            settings.ensure_dirs()
            _print({"status": "initialized", "db": str(settings.db_path), "workspace": str(settings.workspace_root), "reports": str(settings.report_root)})
        elif args.command == "runtime-status":
            _print(runtime.health())
        elif args.command == "status":
            return cmd_status()
        elif args.command == "doctor":
            return cmd_doctor()
        elif args.command == "mission":
            if args.mission_command == "create":
                _print(runtime.create_mission(args.objective, args.source_dir))
            elif args.mission_command == "status":
                _print(runtime.get_mission(args.mission_id))
            elif args.mission_command == "plan":
                _print(runtime.plan_mission(args.mission_id))
            elif args.mission_command == "approve":
                _print(runtime.approve_mission(args.mission_id, not args.reject, "human", args.note, args.decision, args.scope))
            elif args.mission_command == "run":
                _print(runtime.run_mission(args.mission_id))
            elif args.mission_command == "pause":
                _print(runtime.pause(args.mission_id))
            elif args.mission_command == "resume":
                _print(runtime.resume(args.mission_id))
            elif args.mission_command == "rollback":
                _print(runtime.rollback(args.mission_id))
        elif args.command == "evidence":
            _print(runtime.evidence.list(args.mission_id))
        elif args.command == "memory":
            _print(runtime.memory.inspect(args.mission_id))
        elif args.command == "eval":
            _print(runtime.evaluator.list(args.mission_id))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
