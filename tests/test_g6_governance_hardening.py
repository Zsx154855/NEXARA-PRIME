"""G6: Governance & Evidence Hardening Contract Tests."""
from __future__ import annotations


class TestRiskEnforcement:
    """GOV_INVARIANT_01: R0-R4 risk levels enforced."""

    def test_policy_engine_requires_approval_r2_plus(self) -> None:
        from nexara_prime.governance import PolicyEngine
        from nexara_prime.models import RiskLevel
        policy = PolicyEngine()
        assert not policy.requires_approval(RiskLevel.R0)
        assert not policy.requires_approval(RiskLevel.R1)
        assert policy.requires_approval(RiskLevel.R2)
        assert policy.requires_approval(RiskLevel.R3)
        assert policy.requires_approval(RiskLevel.R4)

    def test_r4_actions_blocked(self) -> None:
        from nexara_prime.governance import PolicyEngine
        from nexara_prime.models import RiskLevel
        policy = PolicyEngine()
        ok, _ = policy.allows_tool("any_tool", RiskLevel.R4)
        assert not ok

    def test_safe_mode_restricts_tools(self) -> None:
        from nexara_prime.governance import PolicyEngine
        from nexara_prime.models import RiskLevel
        policy = PolicyEngine()
        ok, _ = policy.allows_tool("file_read", RiskLevel.R1, safe_mode=True)
        assert ok
        ok2, _ = policy.allows_tool("code_exec", RiskLevel.R1, safe_mode=True)
        assert not ok2


class TestAuditTrail:
    """GOV_INVARIANT_02: Audit trail for all approvals."""

    def test_security_audit_ledger_exists(self) -> None:
        from nexara_prime.security_audit import SecurityAuditLedger
        assert SecurityAuditLedger is not None

    def test_secret_scan_script_exists(self) -> None:
        from pathlib import Path
        p = Path(__file__).parent.parent / "scripts/security/scan_hardcoded_secrets.py"
        assert p.exists(), "Secret scanning script must exist"


class TestRecoveryAndRepair:
    """GOV_INVARIANT_04+05: Recovery + repair loop."""

    def test_durable_recovery_has_checkpoint(self) -> None:
        from nexara_prime.recovery import DurableRecovery
        methods = [m for m in dir(DurableRecovery) if not m.startswith("_")]
        has_checkpoint_like = any(
            "checkpoint" in m.lower() or "save" in m.lower() or "snapshot" in m.lower()
            for m in methods
        )
        assert has_checkpoint_like, (
            "DurableRecovery must have checkpoint/save/snapshot capability. Methods: {}".format(methods)
        )

    def test_repair_loop_exists(self) -> None:
        from nexara_prime.repair_loop import RepairLoop
        assert RepairLoop is not None

    def test_escalation_engine_exists(self) -> None:
        from nexara_prime.escalation import EscalationEngine
        assert EscalationEngine is not None


class TestSecretManagement:
    """GOV_INVARIANT_03: Secrets never hardcoded."""

    def test_secret_backends_exist(self) -> None:
        from nexara_prime.secrets import env, keychain, memory
        assert env is not None
        assert keychain is not None
        assert memory is not None


def test_audit_ledger_chain_survives_concurrent_records(tmp_path) -> None:
    """并发 record() 不得破坏哈希链（回归：无锁时两个线程读到同一 tail 导致断链）。"""
    import threading
    from pathlib import Path

    from nexara_prime.db import SQLiteStore
    from nexara_prime.security_audit import SecurityAuditLedger

    store = SQLiteStore(tmp_path / "audit.db")
    ledger = SecurityAuditLedger(store)
    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(25):
                ledger.record("test.concurrent", actor_id=f"w{worker_id}", mission_id=f"m{worker_id}", action=f"step-{i}")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    ok, msg = ledger.verify_chain()
    assert ok, msg
    assert ledger.count() == 100

    # 持久化后重载仍可验证
    reloaded = SecurityAuditLedger(SQLiteStore(tmp_path / "audit.db"))
    assert reloaded.verify_chain()[0] is True
