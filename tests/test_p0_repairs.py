"""P0 Repair verification tests — sandbox escape, approval binding, audit persistence.
NEXARA_PRIME_SECURITY_ENFORCEMENT_AND_RUNTIME_TRUTH_REPAIR_V2_2."""
from __future__ import annotations

import json, os, platform, sys, tempfile, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class ApprovalBindingTests(unittest.TestCase):
    """P0-2: Approval must come from persistent store, not bare boolean."""
    @classmethod
    def setUpClass(cls):
        from nexara_prime.config import Settings
        from nexara_prime.runtime import NexaraRuntime
        cls.settings = Settings.from_env(Path(tempfile.mkdtemp()))
        cls.runtime = NexaraRuntime(cls.settings)

    def test_no_approval_id_rejected(self):
        with self.assertRaises(PermissionError) as ctx:
            self.runtime.tools.invoke("m1", "file_write_report",
                {"path": "test.md", "content": "x"}, "t1", actor_id="test")
        self.assertIn("approval_required", str(ctx.exception))

    def test_fake_approval_id_rejected(self):
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report",
                {"path": "test.md", "content": "x"}, "t1",
                approval_id="fake-nonexistent-id", actor_id="test")

    def test_expired_approval_rejected(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", expires_in_seconds=0)
        time.sleep(0.01)
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report",
                {"path": "test.md", "content": "x"}, "t1",
                approval_id=app.approval_id, actor_id="test")

    def test_wrong_mission_approval_rejected(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", expires_in_seconds=60)
        self.runtime.approvals.decide(app.approval_id, True, "test", "test", "t1", decision="approve_once")
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m2", "file_write_report",
                {"path": "test.md", "content": "x"}, "t1",
                approval_id=app.approval_id, actor_id="test")

    def test_single_action_approval_consumed(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", approval_scope="single_action", expires_in_seconds=60)
        self.runtime.approvals.decide(app.approval_id, True, "test", "test", "t1", decision="approve_once")
        # First use — should succeed
        inv = self.runtime.tools.invoke("m1", "file_write_report",
            {"path": "m1/test.md", "content": "ok"}, "t1",
            approval_id=app.approval_id, actor_id="test")
        self.assertEqual(inv.status, "completed")
        # Second use — should fail (consumed)
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report",
                {"path": "m1/test2.md", "content": "x"}, "t2",
                approval_id=app.approval_id, actor_id="test")

    def test_agent_identity_first_party_defaults(self):
        """G1: AgentIdentity must carry first-party defaults — not model-dependent."""
        from nexara_prime.identity import AgentIdentity, AGENT_DEFAULT_PERMISSIONS
        aid = AgentIdentity()
        self.assertEqual(aid.agent_id, "nexara_prime.agent")
        self.assertEqual(aid.display_name, "NEXARA")
        self.assertEqual(aid.version, "1.0.0")
        self.assertEqual(aid.memory_namespace, "nexara_prime.agent.memory")
        self.assertEqual(len(aid.product_principles), 10)
        self.assertIn("Model independence", aid.product_principles[2])
        self.assertIn("Hermes dependency = 0", aid.product_principles[9])
        self.assertGreater(len(aid.capability_profile), 20)
        self.assertIn("mission.execute", aid.capability_profile)
        # AGENT_DEFAULT_PERMISSIONS must not include admin/secret operations
        self.assertIn("mission.read", AGENT_DEFAULT_PERMISSIONS)
        self.assertNotIn("secret.manage", AGENT_DEFAULT_PERMISSIONS)
        self.assertNotIn("security.admin", AGENT_DEFAULT_PERMISSIONS)
        self.assertNotIn("runtime.control", AGENT_DEFAULT_PERMISSIONS)

    def test_agent_cannot_escalate_security_admin(self):
        from nexara_prime.identity import IdentityStore
        store = IdentityStore()
        self.assertFalse(store.check_permission("u1", "security.admin", is_agent=True))

    def test_legitimate_approval_works(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", approval_scope="mission", expires_in_seconds=60)
        self.runtime.approvals.decide(app.approval_id, True, "test", "test", "t1", decision="approve_mission")
        inv = self.runtime.tools.invoke("m1", "file_write_report",
            {"path": "m1/legit.md", "content": "approved"}, "t1",
            approval_id=app.approval_id, actor_id="test")
        self.assertEqual(inv.status, "completed")

    def test_approval_action_mismatch_rejected(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", expires_in_seconds=60)
        self.runtime.approvals.decide(app.approval_id, True, "human", "test", "t1", decision="approve_once")
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "write_workspace_file",
                {"path": "mismatch.md", "content": "must not write"}, "t1",
                approval_id=app.approval_id, actor_id="runtime")

    def test_approval_executor_mismatch_rejected(self):
        from nexara_prime.models import RiskLevel
        app = self.runtime.approvals.request("m1", "file_write_report", RiskLevel.R2,
            "test", ["test"], "t1", executor_id="runtime", expires_in_seconds=60)
        self.runtime.approvals.decide(app.approval_id, True, "human", "test", "t1", decision="approve_once")
        with self.assertRaises(PermissionError):
            self.runtime.tools.invoke("m1", "file_write_report",
                {"path": "wrong-actor.md", "content": "must not write"}, "t1",
                approval_id=app.approval_id, actor_id="untrusted-agent")


class SandboxEscapeTests(unittest.TestCase):
    """P0-1: Real sandbox escape tests."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_write_outside_workspace_rejected(self):
        from nexara_prime.sandbox_v2 import ProcessConstrainedBackend, SandboxInvocation, _validate_path
        ws = os.path.join(self.tmpdir, "ws")
        os.makedirs(ws, exist_ok=True)
        # Test path validation rejects absolute outside paths
        ok, _ = _validate_path("/private/tmp/escape.txt", ws)
        self.assertFalse(ok, "Absolute path outside workspace must be rejected by path validator")

    def test_pathlib_escape_rejected(self):
        from nexara_prime.sandbox_v2 import _validate_path
        ok, _ = _validate_path("/private/tmp/escape.txt", self.tmpdir)
        self.assertFalse(ok)

    def test_subprocess_escape_rejected(self):
        from nexara_prime.sandbox_v2 import _sanitize_argv
        # Shell injection via subprocess argument should be caught
        args, err = _sanitize_argv(["python3", "-c", "print(1); rm -rf /"])
        self.assertNotEqual(err, "", "Shell metacharacters should be blocked")

    def test_symlink_escape_detected(self):
        from nexara_prime.sandbox_v2 import _validate_path
        link = os.path.join(self.tmpdir, "link")
        try:
            os.symlink("/etc/hosts", link)
            ok, _ = _validate_path("link", self.tmpdir)
            self.assertFalse(ok)
        except OSError:
            pass

    def test_shell_metacharacter_blocked(self):
        from nexara_prime.sandbox_v2 import _sanitize_argv
        args, err = _sanitize_argv(["echo", "hello; rm -rf /"])
        self.assertNotEqual(err, "")

    def test_forbidden_command_blocked(self):
        from nexara_prime.sandbox_v2 import _validate_command
        ok, reason = _validate_command("", ["sudo", "ls"])
        self.assertFalse(ok)

    def test_macos_sandbox_probe(self):
        from nexara_prime.sandbox_v2 import MacOSSandboxBackend, OS_SANDBOX_CAPABLE
        import platform
        sb = MacOSSandboxBackend(self.tmpdir)
        cap = sb.probe_capability()
        if platform.system() == "Darwin":
            self.assertIn(OS_SANDBOX_CAPABLE, cap.flags)

    @unittest.skipUnless(platform.system() == "Darwin", "requires macOS sandbox-exec")
    def test_tool_runtime_blocks_workspace_escape(self):
        from nexara_prime.config import Settings
        from nexara_prime.runtime import NexaraRuntime
        marker = Path("/private/tmp/nexara-tool-runtime-test-escape")
        marker.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = NexaraRuntime(Settings(root / "runtime.db", root / "workspace", root / "reports", "mock", True, "127.0.0.1", 8765))
            result = runtime.tools._code_exec({"code": "__import__('pathlib').Path('/private/tmp/nexara-tool-runtime-test-escape').write_text('escape')"}, 5)
            self.assertFalse(marker.exists(), result)
            self.assertNotEqual(result["returncode"], 0)
            runtime.store.close()
        marker.unlink(missing_ok=True)


class AuditPersistenceTests(unittest.TestCase):
    """P0-5: Audit persistence and chain integrity."""
    def test_empty_chain_with_missions_fails(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        ok, msg = ledger.verify_with_mission_check(has_missions=True)
        self.assertFalse(ok)
        self.assertIn("empty", msg.lower())

    def test_empty_chain_no_missions_passes(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        ok, _ = ledger.verify_with_mission_check(has_missions=False)
        self.assertTrue(ok)

    def test_full_chain_verification(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        for i in range(5):
            ledger.record(f"event_{i}", mission_id="m1")
        ok, msg = ledger.verify_chain()
        self.assertTrue(ok, msg)
        ok2, _ = ledger.verify_with_mission_check(has_missions=True)
        self.assertTrue(ok2)

    def test_tamper_detection_after_delete(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        ledger.record("mission_created", mission_id="m1")
        ledger.record("tool_invoked", mission_id="m1")
        ledger.record("evidence_committed", mission_id="m1")
        # Delete the middle entry
        deleted = ledger._entries.pop(1)
        tampered = ledger.detect_tamper()
        self.assertGreater(len(tampered), 0)

    def test_tamper_detection_after_modify(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        ledger.record("approval_granted", mission_id="m1", decision="approved")
        # Modify decision
        ledger._entries[0].decision = "denied"
        tampered = ledger.detect_tamper()
        self.assertGreater(len(tampered), 0)

    def test_missing_events_detected(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        for i in range(3):
            ledger.record(f"e{i}")
        # Remove first entry — chain should break
        ledger._entries.pop(0)
        # Chain should now be broken since entry 0's prev_hash won't match genesis
        ok, msg = ledger.verify_chain()
        self.assertFalse(ok, f"Chain should be broken after removing entry, got: {msg}")

    def test_order_preserved(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        ledger.record("a")
        ledger.record("b")
        ledger.record("c")
        # Swap order
        ledger._entries[1], ledger._entries[2] = ledger._entries[2], ledger._entries[1]
        tampered = ledger.detect_tamper()
        self.assertGreater(len(tampered), 0)

    @unittest.skipUnless(platform.system() == "Darwin", "requires macOS sandbox-exec")
    def test_real_mission_persists_audit_chain(self):
        from nexara_prime.config import Settings
        from nexara_prime.runtime import NexaraRuntime
        from nexara_prime.security_audit import SecurityAuditLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "workspace" / "source"
            source.mkdir(parents=True)
            (source / "README.md").write_text("audit acceptance", encoding="utf-8")
            runtime = NexaraRuntime(Settings(root / "runtime.db", root / "workspace", root / "reports", "mock", True, "127.0.0.1", 8765))
            mission = runtime.create_mission("Create a verified local report", str(source))
            planned = runtime.plan_mission(mission.mission_id)
            self.assertIsNotNone(planned.pending_approval_id)
            runtime.approve_mission(mission.mission_id, decision="approve_once", actor="human")
            completed = runtime.run_mission(mission.mission_id)
            self.assertEqual(completed.state, "Completed")
            ledger = SecurityAuditLedger(runtime.store)
            self.assertGreater(ledger.count(), 0)
            ok, message = ledger.verify_with_mission_check(has_missions=True)
            self.assertTrue(ok, message)
            self.assertTrue(all(entry["mission_id"] == mission.mission_id for entry in ledger.list_entries(mission_id=mission.mission_id)))
            runtime.store.close()


class CLICoverageTests(unittest.TestCase):
    """P1: CLI commands work with new APIs."""
    def test_status_runs(self):
        from nexara_prime.cli import main
        rc = main(["status"])
        self.assertEqual(rc, 0)

    def test_doctor_runs(self):
        from nexara_prime.cli import main
        rc = main(["doctor"])
        self.assertEqual(rc, 0)

    def test_security_status(self):
        from nexara_prime.cli import main
        rc = main(["security", "status"])
        self.assertEqual(rc, 0)

    def test_security_audit_verify(self):
        from nexara_prime.cli import main
        rc = main(["security", "audit", "verify"])
        self.assertEqual(rc, 0)

    def test_connectors_list(self):
        from nexara_prime.cli import main
        rc = main(["connectors", "list"])
        self.assertEqual(rc, 0)

    def test_secrets_list(self):
        from nexara_prime.cli import main
        rc = main(["secrets", "list"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
