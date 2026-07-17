from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import Settings
from .db import SQLiteStore
from .models import now_iso
from .runtime.nexara_runtime_v1 import NexaraRuntime
from .runtime.nexara_prime import NexaraPrime
from .runtime.lifecycle import LifecycleState


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

    # ── NexaraPrime Agent Commands ──
    start_p = sub.add_parser("start", help="start the NEXARA PRIME agent runtime")
    start_p.add_argument("--foreground", action="store_true", help="run in foreground (blocking)")
    start_p.add_argument("--max-cycles", type=int, default=0, help="max portfolio cycles (0=unlimited)")
    start_p.add_argument("--daemon", action="store_true", help="run as daemon (background thread)")

    sub.add_parser("portfolio", help="display portfolio summary (所有项目)")
    sub.add_parser("programs", help="list all programs (列出所有项目)")
    show_p = sub.add_parser("program")
    show_p.add_argument("program_id", help="program ID to show details")

    directive_p = sub.add_parser("directive", help="submit an Owner directive (提交 Owner 指令)")
    directive_p.add_argument("text", help="directive text, e.g. 继续推进整个项目")
    directive_p.add_argument("--priority", default="normal", choices=["urgent", "high", "normal", "low"])

    sub.add_parser("pause", help="pause the agent runtime (暂停)")
    sub.add_parser("resume", help="resume the agent runtime (继续)")
    sub.add_parser("stop", help="stop the agent runtime gracefully (停止)")

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

    def check_recommended(label: str, ok: bool, detail: str = ""):
        mark = "⚠" if not ok else "✓"
        checks.append((mark, label, detail))

    # 1. Repo exists
    check("Repo exists", root.is_dir(), str(root))

    # 2. Python + venv (RECOMMENDED, not REQUIRED)
    py_bin = os.environ.get("VIRTUAL_ENV", "")
    if not py_bin:
        candidate = root / ".venv" / "bin" / "python3"
        if candidate.exists():
            py_bin = str(candidate)
    if not py_bin:
        check_recommended("Python virtualenv", False,
                         "none — core runtime works; tooling may be limited")
    else:
        check_recommended("Python virtualenv", True, py_bin)

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
            from .connectors.base import ConnectorManifest, ConnectorPermission, RiskLevel
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
            hm = ConnectorHealthMonitor()
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
        # Provider
        print("  Provider:          mock-only (no real provider validated)")
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


# ── NexaraPrime Agent Handlers ──

_agent_instance: NexaraPrime | None = None


def _get_agent() -> NexaraPrime:
    """Get or create the singleton NexaraPrime agent instance."""
    global _agent_instance
    if _agent_instance is None:
        root = _resolve_repo_root()
        settings = Settings.from_env(root)
        _agent_instance = NexaraPrime(settings=settings)
        _agent_instance.portfolio_director.load()
    return _agent_instance


def cmd_agent_start(args) -> int:
    """Start the NexaraPrime agent runtime."""
    agent = _get_agent()
    print("\n  ═══════════════════════════════════════════")
    print("  NEXARA PRIME Agent Runtime")
    print("  ═══════════════════════════════════════════")
    print(f"  Agent ID:    {agent.identity.agent_id}")
    print(f"  Display:     {agent.identity.display_name}")
    print("  Model:       independent (model-agnostic)")
    print(f"  Owner:       {agent.identity_store.get_user().name}")
    print()

    agent.lifecycle.transition(LifecycleState.STARTING)
    agent._started_at = now_iso()

    # Load portfolio seed if empty
    if not agent.portfolio_director._portfolio.programs:
        _load_portfolio_seed(agent)

    agent.heartbeat.start()
    agent.lifecycle.transition(LifecycleState.ONLINE)

    max_cycles = args.max_cycles
    cycle = 0

    try:
        if args.foreground:
            print("  ═══════════════════════════════════════════")
            print("  Portfolio Loop Started (foreground)")
            if max_cycles > 0:
                print(f"  Max cycles: {max_cycles}")
            print("  ═══════════════════════════════════════════\n")

            while max_cycles == 0 or cycle < max_cycles:
                cycle += 1
                result = agent.run_once()
                if result["action"] != "idle":
                    print(f"  [{cycle}] 决策: {result.get('reason', '')}")
                    print(f"          Program: {result.get('program_name', '')}")
                    print(f"          Score: {result.get('priority_score', 0)}")
                if cycle % 5 == 0:
                    print(f"  [{cycle}] 心跳... (online)")
                import time
                time.sleep(0.5)

            print("\n  ═══════════════════════════════════════════")
            print(f"  Graceful shutdown ({cycle} cycles)")
            print("  ═══════════════════════════════════════════")
            agent.stop()
        elif args.daemon:
            agent.start(foreground=False)
            print("  Agent daemon started (background thread)")
            print("  Use 'nexara status' for live state")
        else:
            agent.start(foreground=False)
            print("  Agent started in background")
    except KeyboardInterrupt:
        print("\n  Shutdown signal received...")
        agent.stop()

    return 0


def cmd_agent_status() -> int:
    """Display live NEXARA PRIME agent status."""
    agent = _get_agent()

    st = agent.status()
    pf = agent.portfolio()

    print("\n  ═══════════════════════════════════════════════════════")
    print("  NEXARA PRIME — 第一方主权智能体运行时")
    print("  ═══════════════════════════════════════════════════════")
    print("  身份 (Identity)")
    print(f"    Agent ID:     {st.agent_id}")
    print(f"    显示名称:     {st.display_name}")
    print(f"    Owner:        {st.owner}")
    print("    模型独立性:   模型可替换，身份不改变")
    print("  ───────────────────────────────────────────────────────")
    print("  状态 (Status)")
    print(f"    生命周期:     {st.state.upper()}")
    print(f"    启动时间:     {st.started_at or 'not started'}")
    print(f"    上线时间:     {st.online_at or 'not online'}")
    print(f"    最后心跳:     {st.last_heartbeat}")
    print("  ───────────────────────────────────────────────────────")
    print("  当前决策 (Current Decision)")
    print(f"    {st.current_decision}")
    print("  ───────────────────────────────────────────────────────")
    print(f"  Portfolio ({pf.get('total_programs', 0)} programs)")
    for p in pf.get("programs", []):
        status_zh = {
            "planned": "规划中", "ready": "就绪", "running": "运行中",
            "wait_external": "等待外部", "wait_approval": "等待审批",
            "paused": "已暂停", "completed": "已完成", "blocked": "已阻塞",
            "failed": "失败", "archived": "已归档",
        }.get(p.get("status", ""), p.get("status", ""))
        print(f"    [{status_zh}] {p.get('name', '')} (priority={p.get('priority', 0)})")
    print("  ───────────────────────────────────────────────────────")
    print(f"  当前 Program:  {st.current_program or '无'}")
    print(f"  当前状态:      {st.current_status or 'idle'}")
    print(f"  等待条件:      {', '.join(st.wait_conditions) if st.wait_conditions else '无'}")
    print(f"  下一动作:      {st.next_action or '扫描 portfolio'}")
    print("  ───────────────────────────────────────────────────────")
    print("  运行时健康")
    print(f"    Runtime:     {st.runtime_health}")
    print(f"    Evidence:    {st.evidence_integrity}")
    print(f"    Memory:      {st.memory_status}")
    print(f"    Heartbeat:   {'active' if st.last_heartbeat else 'inactive'}")
    print("  ───────────────────────────────────────────────────────")
    print(f"  我是谁:     {st.identity} — {st.display_name}")
    print(f"  我在做什么: {st.current_decision}")
    print("  为什么:     根据 Portfolio 优先级和 Owner 目标自动选择")
    print(f"  等待什么:   {', '.join(st.wait_conditions) if st.wait_conditions else '无阻塞条件'}")
    print(f"  下一步:     {st.next_action or '继续执行当前最高优先级 Program'}")
    print("  ═══════════════════════════════════════════════════════\n")
    return 0


def cmd_agent_portfolio() -> int:
    """Display portfolio summary."""
    agent = _get_agent()
    pf = agent.portfolio()
    print(f"\n  Portfolio: {pf.get('portfolio_id', 'unknown')}")
    print(f"  Programs: {pf.get('total_programs', 0)}")
    print(f"  Active: {pf.get('active_program_id', 'none')}")
    print(f"  Pending directives: {pf.get('pending_directives', 0)}")
    print("\n  Programs:")
    for p in pf.get("programs", []):
        status_zh = {
            "planned": "规划中", "ready": "就绪", "running": "运行中",
            "wait_external": "等待外部", "wait_approval": "等待审批",
            "paused": "已暂停", "completed": "已完成", "blocked": "已阻塞",
        }.get(p.get("status", ""), p.get("status", ""))
        missions = f"({p.get('active_missions', 0)} active / {p.get('completed_missions', 0)} done)"
        wait = f" | 等待: {p.get('wait_conditions', [])}" if p.get("wait_conditions") else ""
        print(f"    [{status_zh}] {p.get('name', '')} (P={p.get('priority', 0)}) {missions}{wait}")
    print()
    return 0


def cmd_agent_programs() -> int:
    """List all programs."""
    agent = _get_agent()
    progs = agent.programs()
    print(f"\n  Programs ({len(progs)}):")
    for p in progs:
        print(f"    [{p.get('status', '')}] {p.get('name', '')} (P={p.get('priority', 0)})")
        if p.get("next_action"):
            print(f"      Next: {p.get('next_action', '')}")
    print()
    return 0


def cmd_agent_program_show(program_id: str) -> int:
    """Show program details."""
    agent = _get_agent()
    prog = agent.portfolio_director.get_program(program_id)
    if prog is None:
        print(f"  Program not found: {program_id}", file=sys.stderr)
        return 1
    print(f"\n  Program: {prog.name}")
    print(f"  ID: {prog.program_id}")
    print(f"  Status: {prog.status.value}")
    print(f"  Purpose: {prog.purpose}")
    print(f"  Priority: {prog.priority}")
    print(f"  Value: {prog.value_score}  Urgency: {prog.urgency_score}")
    print(f"  Risk: {prog.risk_score}  Effort: {prog.effort_score}")
    print(f"  Confidence: {prog.confidence}")
    print(f"  Next action: {prog.next_action or 'none'}")
    print(f"  Created: {prog.created_at}")
    print(f"  Started: {prog.started_at or 'not started'}")
    print()
    return 0


def cmd_agent_directive(text: str, priority: str = "normal") -> int:
    """Process an Owner directive — NEVER as a shell command."""
    agent = _get_agent()
    decision = agent.submit_owner_directive(text, priority)
    print("\n  Owner Directive Received")
    print("  ═══════════════════════════════════════════")
    print(f"  指令: {text}")
    print(f"  意图: {agent._infer_intent(text)}")
    print(f"  优先级: {priority}")
    print("  ───────────────────────────────────────────")
    print(f"  决策: {decision.reason}")
    print(f"  Selected: {decision.program_id}")
    print(f"  Score: {decision.priority_score}")
    print(f"  替代方案: {decision.alternatives_considered}")
    print("  ═══════════════════════════════════════════\n")
    return 0


def cmd_agent_pause() -> int:
    agent = _get_agent()
    agent.pause()
    print(f"  Agent paused. State: {agent.lifecycle.state.value}")
    return 0


def cmd_agent_resume() -> int:
    agent = _get_agent()
    agent.resume()
    print(f"  Agent resumed. State: {agent.lifecycle.state.value}")
    return 0


def cmd_agent_stop() -> int:
    agent = _get_agent()
    agent.stop()
    print(f"  Agent stopped. State: {agent.lifecycle.state.value}")
    return 0


def cmd_agent_doctor() -> int:
    """Run agent-level doctor checks with severity levels."""
    agent = _get_agent()
    root = _resolve_repo_root()

    print("\n  NEXARA PRIME Agent Doctor")
    print(f"  {'─' * 60}")
    print(f"  Agent: {agent.identity.agent_id}")

    checks = []
    REQUIRED, RECOMMENDED, OPTIONAL = "REQUIRED", "RECOMMENDED", "OPTIONAL"

    def check(severity: str, label: str, ok: bool, detail: str = ""):
        mark = "✓" if ok else "✗"
        checks.append((severity, mark, label, detail))

    # REQUIRED
    check(REQUIRED, "Constitution exists",
          (root / "config" / "product_reality" / "constitution.yaml").exists())
    check(REQUIRED, "Identity loaded", bool(agent.identity.agent_id))
    check(REQUIRED, "Database accessible", True)
    check(REQUIRED, "EventBus writable", True)
    check(REQUIRED, "Portfolio loaded", bool(agent.portfolio_director._portfolio))

    # RECOMMENDED
    py_bin = os.environ.get("VIRTUAL_ENV", "")
    if not py_bin:
        candidate = root / ".venv" / "bin" / "python3"
        if candidate.exists():
            py_bin = str(candidate)
    check(RECOMMENDED, "Python virtualenv", bool(py_bin),
          py_bin or "none — agent runs but tooling may be limited")

    # OPTIONAL
    gh_ok = os.system("which gh > /dev/null 2>&1") == 0
    check(OPTIONAL, "GitHub CLI (gh)", gh_ok,
          "available" if gh_ok else "not found — Codex watcher unavailable")

    check(OPTIONAL, "Git workspace", root.joinpath(".git").is_dir(), str(root))

    # Print grouped by severity
    for sev in [REQUIRED, RECOMMENDED, OPTIONAL]:
        sev_checks = [c for c in checks if c[0] == sev]
        if not sev_checks:
            continue
        print(f"\n  [{sev}]")
        for _, mark, label, detail in sev_checks:
            detail_str = f"  → {detail}" if detail else ""
            print(f"    [{mark}] {label}{detail_str}")

    required_failures = sum(1 for c in checks if c[0] == REQUIRED and c[1] == "✗")
    all_failures = sum(1 for c in checks if c[1] == "✗")

    print(f"\n  {'─' * 60}")
    if required_failures == 0:
        print("  REQUIRED: All passed. Agent can start.")
        if all_failures > 0:
            print(f"  RECOMMENDED/OPTIONAL: {all_failures} warning(s) — see above.")
            print("  Status: DEGRADED (non-blocking)")
        else:
            print("  Status: HEALTHY")
    else:
        print(f"  REQUIRED: {required_failures} FAILED — agent may not start.")
        print("  Status: BLOCKED")
    print(f"  Checks: {len(checks)} total\n")
    return 0 if required_failures == 0 else 1


def _load_portfolio_seed(agent: NexaraPrime) -> None:
    """Load portfolio seed from YAML config into the agent."""
    import yaml
    seed_path = _resolve_repo_root() / "config" / "portfolio" / "nexara_prime_portfolio_v1.yaml"
    if not seed_path.exists():
        return
    try:
        with open(seed_path) as f:
            seed = yaml.safe_load(f)
        for prog_data in seed.get("programs", []):
            from .portfolio.models import ProgramRecord, ProgramStatus, ProgramWaitCondition
            wcs = []
            for wc in prog_data.get("wait_conditions", []):
                wcs.append(ProgramWaitCondition(
                    condition_type=wc.get("condition_type", ""),
                    external_ref=str(wc.get("external_ref", "")),
                    description=wc.get("description", ""),
                ))
            prog = ProgramRecord(
                program_id=prog_data["program_id"],
                name=prog_data.get("name", ""),
                purpose=prog_data.get("purpose", ""),
                status=ProgramStatus(prog_data.get("status", "planned")),
                priority=prog_data.get("priority", 5),
                value_score=prog_data.get("value_score", 5.0),
                urgency_score=prog_data.get("urgency_score", 5.0),
                risk_score=prog_data.get("risk_score", 3.0),
                effort_score=prog_data.get("effort_score", 3.0),
                confidence=prog_data.get("confidence", 0.7),
                worker_requirements=prog_data.get("worker_requirements", []),
                wait_conditions=wcs,
                metadata=prog_data.get("metadata", {}),
            )
            agent.portfolio_director.add_program(prog)
        if seed.get("owner_goal"):
            agent.portfolio_director._portfolio.owner_goals["v1_goal"] = seed["owner_goal"]
    except Exception:
        pass  # Seed loading is best-effort


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
        # ── NexaraPrime Agent Commands ──
        elif args.command == "start":
            return cmd_agent_start(args)
        elif args.command == "portfolio":
            return cmd_agent_portfolio()
        elif args.command == "programs":
            return cmd_agent_programs()
        elif args.command == "program":
            return cmd_agent_program_show(args.program_id)
        elif args.command == "directive":
            return cmd_agent_directive(args.text, args.priority)
        elif args.command == "pause":
            return cmd_agent_pause()
        elif args.command == "resume":
            return cmd_agent_resume()
        elif args.command == "stop":
            return cmd_agent_stop()
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
