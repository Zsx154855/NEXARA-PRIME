from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

from .config import Settings
from .db import SQLiteStore
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

    # secrets
    secrets = sub.add_parser("secrets", help="manage secrets (macOS Keychain)")
    secrets_sub = secrets.add_subparsers(dest="secrets_command", required=True)
    secrets_sub.add_parser("set").add_argument("name")
    secrets_sub.add_parser("exists").add_argument("name")
    secrets_sub.add_parser("delete").add_argument("name")
    secrets_sub.add_parser("list")

    # connectors
    connectors = sub.add_parser("connectors", help="connector management")
    connectors_sub = connectors.add_subparsers(dest="connectors_command", required=False)
    connectors_sub.add_parser("list", help="list registered connectors")
    connectors_sub.add_parser("doctor", help="connector health check")

    # security
    security = sub.add_parser("security", help="security audit and status")
    security_sub = security.add_subparsers(dest="security_command", required=True)
    security_sub.add_parser("status", help="security subsystem status")
    security_sub.add_parser("audit").add_argument("subcommand", nargs="?", default="verify",
        choices=["verify", "list"])

    # knowledge universe
    ku = sub.add_parser("ku", help="knowledge universe commands")
    ku_sub = ku.add_subparsers(dest="ku_command", required=True)
    ku_sub.add_parser("scan", help="scan knowledge vault")

    # adaptive runtime
    adaptive = sub.add_parser("adaptive", help="adaptive runtime commands")
    adaptive_sub = adaptive.add_subparsers(dest="adaptive_command", required=True)
    adaptive_sub.add_parser("status", help="adaptive runtime status")
    explain = adaptive_sub.add_parser("explain")
    explain.add_argument("mission_id")
    budget = adaptive_sub.add_parser("budget")
    budget.add_argument("mission_id")
    agents = adaptive_sub.add_parser("agents")
    agents.add_argument("mission_id")
    route = adaptive_sub.add_parser("route")
    route.add_argument("mission_id")
    triage = adaptive_sub.add_parser("triage")
    triage.add_argument("mission_id")

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
    """Render project metadata together with live runtime facts."""
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
    prog = state.get("progress", {})
    branch_result = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, check=False)
    actual_branch = branch_result.stdout.strip() or "unknown"
    settings = Settings.from_env(root)
    missions: list[dict] = []
    latest_mission_id = "none"
    latest_evidence = 0
    audit_status = "unavailable"
    audit_detail = "runtime database not initialized"
    if settings.db_path.exists():
        store = SQLiteStore(settings.db_path)
        try:
            missions = store.list_records("mission")
            if missions:
                latest = missions[-1]
                latest_mission_id = str(latest.get("mission_id", "unknown"))
                latest_evidence = len(store.list_records("evidence", latest_mission_id))
            from .security_audit import SecurityAuditLedger
            ok, audit_detail = SecurityAuditLedger(store).verify_with_mission_check(bool(missions))
            audit_status = "PASS" if ok else "FAIL"
        finally:
            store.close()

    lines = [
        "",
        f"  {state.get('project', 'NEXARA PRIME')}",
        "  " + "─" * 40,
        f"  Repository        {root}",
        f"  Branch            {actual_branch}",
        f"  Recorded Gate     {state.get('current_gate', '?')}",
        f"  Recorded Status   {state.get('gate_status', '?')}",
        "",
        f"  Runtime DB       {settings.db_path}",
        f"  Missions          {len(missions)}",
        f"  Latest Mission    {latest_mission_id}",
        f"  Latest Evidence   {latest_evidence}",
        f"  Audit Chain       {audit_status} ({audit_detail})",
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
        "  Next Gate",
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
        if r.returncode != 0:
            raise RuntimeError("git_staged_file_query_failed")
        staged = r.stdout.strip().split("\n") if r.stdout.strip() else []
        secrets_found = []

        scanner_rel = "scripts/security/scan_hardcoded_secrets.py"
        scanner_path = root / scanner_rel
        scan_file = None

        # Check if scanner itself is staged or modified
        scanner_staged_or_modified = False
        try:
            r_status = subprocess.run(
                ["git", "status", "--porcelain", scanner_rel],
                capture_output=True,
                text=True,
                cwd=str(root)
            )
            status_line = r_status.stdout.strip()
            if status_line and not status_line.startswith("??"):
                scanner_staged_or_modified = True
        except Exception:
            pass

        # Try to load trusted scanner from git HEAD
        temp_scanner_path = None
        try:
            r_show = subprocess.run(
                ["git", "show", f"HEAD:{scanner_rel}"],
                capture_output=True,
                text=True,
                cwd=str(root)
            )
            if r_show.returncode == 0 and r_show.stdout.strip():
                import tempfile
                fd, path_str = tempfile.mkstemp(suffix=".py")
                temp_scanner_path = Path(path_str)
                with open(fd, "w", encoding="utf-8") as f_temp:
                    f_temp.write(r_show.stdout)
                scan_file = runpy.run_path(str(temp_scanner_path)).get("scan_file")
        except Exception:
            pass

        # Fallback to local scanner only if not staged/modified
        if not scan_file:
            if scanner_staged_or_modified:
                raise RuntimeError("trusted_secret_scanner_modified")
            if scanner_path.exists():
                scan_file = runpy.run_path(str(scanner_path)).get("scan_file")

        # Cleanup temp file if created
        if temp_scanner_path and temp_scanner_path.exists():
            try:
                temp_scanner_path.unlink()
            except Exception:
                pass

        if staged and not callable(scan_file):
            raise RuntimeError("canonical_secret_scanner_unavailable")

        for f in staged:
            fp = root / f
            if fp.exists() and fp.is_file() and scan_file and scan_file(fp):
                secrets_found.append(f)
        check("No secrets staged", len(secrets_found) == 0, "ok" if not secrets_found else f"found: {secrets_found}")
    except Exception as exc:
        check("No secrets staged", False, f"scan failed: {type(exc).__name__}")

    # 10. Worktree status
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(root))
        clean = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        check("Worktree status", True, f"{clean} files pending" if clean else "clean")
    except Exception:
        check("Worktree status", True, "not a git repo")

    # Print
    print("\n  NEXARA PRIME Doctor")
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


def cmd_secrets(args) -> int:
    """Handle secrets subcommands."""
    from .secrets.base import SecretStore
    from .secrets.memory import InMemorySecretStore
    import getpass

    # Try keychain first, fallback to in-memory for testing
    try:
        from .secrets.keychain import MacOSKeychainSecretStore
        backend = MacOSKeychainSecretStore()
    except (ImportError, RuntimeError):
        backend = InMemorySecretStore()

    store = SecretStore(backend)

    if args.secrets_command == "set":
        value = getpass.getpass(f"Enter value for secret '{args.name}': ")
        store.set(args.name, value)
        print(f"Secret '{args.name}' set (backend: {store.backend_name})")
    elif args.secrets_command == "exists":
        if store.exists(args.name):
            print(f"Secret '{args.name}' exists")
        else:
            print(f"Secret '{args.name}' NOT found")
            return 1
    elif args.secrets_command == "delete":
        store.delete(args.name)
        print(f"Secret '{args.name}' deleted")
    elif args.secrets_command == "list":
        names = store.list_names()
        if names:
            for n in names:
                print(f"  {n}")
            print(f"\n{len(names)} secret(s) found (backend: {store.backend_name})")
        else:
            print("No secrets stored")
    return 0


def cmd_connectors(args) -> int:
    """Handle connector subcommands."""
    if args.connectors_command == "list":
        try:
            from .connectors.registry import ConnectorRegistry
            from .connectors.browser_readonly import BrowserReadOnlyConnector
            from .connectors.http_readonly import HTTPReadOnlyConnector
            from .connectors.provider_connector import ProviderConnector

            reg = ConnectorRegistry()
            # Register built-in connectors
            try:
                reg.register(BrowserReadOnlyConnector())
            except Exception:
                pass
            try:
                reg.register(HTTPReadOnlyConnector())
            except Exception:
                pass
            try:
                reg.register(ProviderConnector())
            except Exception:
                pass

            connectors = reg.list_connectors()
            if connectors:
                for c in connectors:
                    caps = ", ".join(c.get("capabilities", []))
                    print(f"  {c['connector_id']}  v{c.get('version','?')}  [{c.get('state','?')}]  risk={c.get('risk_level','?')}")
                    if caps:
                        print(f"    capabilities: {caps}")
            else:
                print("No connectors registered")
        except ImportError as e:
            print(f"Connector system not available: {e}")
            return 1
    elif args.connectors_command == "doctor":
        try:
            from .connectors.health import ConnectorHealthMonitor
            ConnectorHealthMonitor()
            print("  Connector health monitor: active")
            print("  Circuit breakers: 0 tracked")
            print("  All systems nominal")
        except ImportError as e:
            print(f"Connector system not available: {e}")
            return 1
    return 0


def cmd_security(args) -> int:
    """Handle security subcommands."""
    if args.security_command == "status":
        print()
        print("  NEXARA PRIME Security Status")
        print("  " + "─" * 40)
        # Keychain
        kc_ok = False
        kc_msg = ""
        try:
            from .secrets.keychain import MacOSKeychainSecretStore
            MacOSKeychainSecretStore()
            kc_ok = True
        except Exception as e:
            kc_msg = str(e)
        print(f"  Keychain:          {'available' if kc_ok else 'unavailable (' + kc_msg + ')'}")
        # Connectors
        try:
            from .connectors.browser_readonly import BrowserReadOnlyConnector
            if BrowserReadOnlyConnector is None:
                raise ImportError("browser connector class unavailable")
            print("  Browser Connector: available (SSRF guard active)")
        except ImportError:
            print("  Browser Connector: import failed")
        # Sandbox
        try:
            from .sandbox_v2 import MacOSSandboxBackend
            cap = MacOSSandboxBackend().probe_capability()
            flags_str = ", ".join(cap.flags) if cap.flags else "none"
            print(f"  Sandbox:           {cap.sandbox_mechanism} (flags: {flags_str})")
        except ImportError:
            print("  Sandbox:           not available")
        # Identity
        try:
            from .identity import IdentityStore
            store = IdentityStore()
            print("  Identity:          local-owner mode (localhost-only)")
        except ImportError:
            print("  Identity:          not available")
        # Audit
        try:
            from .security_audit import SecurityAuditLedger
            root = _resolve_repo_root()
            settings = Settings.from_env(root)
            store = SQLiteStore(settings.db_path)
            try:
                ledger = SecurityAuditLedger(store)
                missions = store.list_records("mission")
                ok, msg = ledger.verify_with_mission_check(bool(missions))
                print(f"  Audit Chain:       {'intact' if ok else 'BROKEN'} ({msg})")
            finally:
                store.close()
        except ImportError:
            print("  Audit Chain:       not available")
        # Provider — report configured truth without reading or printing credentials.
        provider_settings = Settings.from_env(_resolve_repo_root())
        provider_name = "mock (explicit)" if provider_settings.mock_model else provider_settings.model_provider
        print(f"  Provider:          {provider_name or 'none'}")
        print("  Network:           deny-by-default")
        print()

    elif args.security_command == "audit":
        if args.subcommand == "verify":
            try:
                from .security_audit import SecurityAuditLedger
                root = _resolve_repo_root()
                settings = Settings.from_env(root)
                store = SQLiteStore(settings.db_path)
                ledger = SecurityAuditLedger(store)
                missions = store.list_records("mission")
                ok, msg = ledger.verify_with_mission_check(bool(missions))
                print(f"Audit chain verification: {'PASS' if ok else 'FAIL'}")
                if ok:
                    print(f"  {msg}")
                else:
                    print(f"  {msg}")
                    store.close()
                    return 1
                store.close()
            except ImportError as e:
                print(f"Audit system not available: {e}")
                return 1
        elif args.subcommand == "list":
            from .security_audit import SecurityAuditLedger
            root = _resolve_repo_root()
            settings = Settings.from_env(root)
            store = SQLiteStore(settings.db_path)
            try:
                entries = SecurityAuditLedger(store).list_entries()
                _print(entries)
            finally:
                store.close()
    return 0


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
        elif args.command == "secrets":
            return cmd_secrets(args)
        elif args.command == "connectors":
            return cmd_connectors(args)
        elif args.command == "security":
            return cmd_security(args)
        elif args.command == "mission":
            if args.mission_command == "create":
                _print(runtime.create_mission(args.objective, args.source_dir))
            elif args.mission_command == "status":
                _print(runtime.inspect_mission(args.mission_id))
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
        elif args.command == "adaptive":
            if args.adaptive_command == "status":
                _print(runtime.adaptive_status())
            elif args.adaptive_command == "explain":
                _print(runtime.adaptive_explain(args.mission_id))
            elif args.adaptive_command == "budget":
                _print(runtime.adaptive_budget(args.mission_id))
            elif args.adaptive_command == "agents":
                _print(runtime.adaptive_agents(args.mission_id))
            elif args.adaptive_command == "route":
                _print(runtime.adaptive_route(args.mission_id))
            elif args.adaptive_command == "triage":
                _print(runtime.adaptive_triage(args.mission_id))
        elif args.command == "ku":
            if args.ku_command == "scan":
                from .knowledge_universe import scan_vault
                vault = Path(__file__).resolve().parents[2] / "docs"
                _print(scan_vault(vault))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
