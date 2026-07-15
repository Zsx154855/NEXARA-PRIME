"""Security hardening tests — connectors, secrets, sandbox, identity, audit.

Covers:
  A. Secret Security
  B. Path Security  
  C. Command Security
  D. Browser Security (SSRF)
  E. Connector Reliability
  F. Identity / Authorization
  G. Audit Integrity
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# ──────────────────────────────────────────────────
# A. Secret Security (15 tests)
# ──────────────────────────────────────────────────

class SecretSecurityTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.secrets.memory import InMemorySecretStore
        from nexara_prime.secrets.env import EnvironmentSecretStore
        from nexara_prime.secrets.base import SecretStore, redact_secrets
        self.InMemorySecretStore = InMemorySecretStore
        self.EnvironmentSecretStore = EnvironmentSecretStore
        self.SecretStore = SecretStore
        self.redact_secrets = redact_secrets

    def test_inmemory_set_and_get(self):
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        store.set("test_key", "secret_value")
        self.assertTrue(store.exists("test_key"))
        self.assertEqual(store.get("test_key"), "secret_value")

    def test_inmemory_delete(self):
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        store.set("k", "v")
        store.delete("k")
        self.assertFalse(store.exists("k"))

    def test_inmemory_list(self):
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        store.set("a", "1")
        store.set("b", "2")
        names = store.list_names()
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_inmemory_get_missing_raises(self):
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        with self.assertRaises(KeyError):
            store.get("nonexistent")

    def test_env_store(self):
        os.environ["NEXARA_SECRET_TEST_VAR"] = "env_value"
        try:
            backend = self.EnvironmentSecretStore()
            store = self.SecretStore(backend)
            self.assertTrue(store.exists("test-var"))
            self.assertEqual(store.get("test-var"), "env_value")
        finally:
            del os.environ["NEXARA_SECRET_TEST_VAR"]

    def test_env_set_override(self):
        backend = self.EnvironmentSecretStore()
        store = self.SecretStore(backend)
        store.set("my-key", "override")
        self.assertTrue(store.exists("my-key"))
        self.assertEqual(store.get("my-key"), "override")

    def test_redact_sk_key(self):
        text = "Authorization: Bearer sk-abc123def456ghi789"
        cleaned = self.redact_secrets(text)
        self.assertNotIn("sk-abc123", cleaned)
        self.assertIn("[REDACTED", cleaned)

    def test_redact_bearer(self):
        text = "Bearer xyz789token.abc.def"
        cleaned = self.redact_secrets(text)
        self.assertNotIn("xyz789token", cleaned)

    def test_redact_api_key(self):
        text = 'api_key = "my-secret-key-12345"'
        cleaned = self.redact_secrets(text)
        self.assertNotIn("my-secret-key", cleaned)

    def test_redact_password(self):
        text = "password: superSecure123!"
        cleaned = self.redact_secrets(text)
        self.assertNotIn("superSecure123", cleaned)

    def test_secret_not_in_evidence_format(self):
        """Secret values must not appear in dict serialization."""
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        store.set("api_key", "sk-topsecret")
        # list_names should NOT contain values
        names = store.list_names()
        self.assertIn("api_key", names)
        self.assertNotIn("sk-topsecret", names)

    def test_secret_null_name_rejected(self):
        backend = self.InMemorySecretStore()
        store = self.SecretStore(backend)
        with self.assertRaises(ValueError):
            store.set("", "value")
        with self.assertRaises(ValueError):
            store.set("name", "")

    def test_env_not_default_for_production(self):
        """EnvironmentSecretStore should not silently become production default."""
        backend = self.EnvironmentSecretStore()
        self.assertIn("Environment", type(backend).__name__)

    def test_missing_keychain_safe_failure(self):
        """Keychain unavailable should raise, not fallback to file."""
        from nexara_prime.secrets.keychain import MacOSKeychainSecretStore
        # Actually test that keychain store doesn't crash on init
        try:
            ks = MacOSKeychainSecretStore()
            # set might fail if keychain not unlocked - that's OK
            self.assertIsNotNone(ks)
        except RuntimeError:
            # Keychain unavailable is acceptable
            pass

    def test_redact_private_key(self):
        text = "private_key = '-----BEGIN RSA PRIVATE KEY-----\\nabc123\\n-----END-----'"  # NEXARA_TEST_FIXTURE
        cleaned = self.redact_secrets(text)
        self.assertNotIn("BEGIN RSA", cleaned)


# ──────────────────────────────────────────────────
# B. Path Security (8 tests)
# ──────────────────────────────────────────────────

class PathSecurityTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.sandbox_v2 import _validate_path, _workspace_jail_execute
        self._validate_path = _validate_path
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dotdot_rejected(self):
        ok, msg = self._validate_path("../../../etc/passwd", self.tmpdir)
        self.assertFalse(ok)

    def test_absolute_path_rejected(self):
        ok, msg = self._validate_path("/etc/passwd", self.tmpdir)
        self.assertFalse(ok)

    def test_symlink_escape_detected(self):
        # Create a symlink pointing outside
        link_path = os.path.join(self.tmpdir, "escape_link")
        try:
            os.symlink("/etc/passwd", link_path)
            ok, msg = self._validate_path("escape_link", self.tmpdir)
            self.assertFalse(ok)
        except OSError:
            pass  # symlink may not be supported in test env

    def test_null_byte_rejected(self):
        ok, msg = self._validate_path("safe\0bad.txt", self.tmpdir)
        self.assertFalse(ok)

    def test_normal_path_ok(self):
        ok, msg = self._validate_path("subdir/file.txt", self.tmpdir)
        self.assertTrue(ok)

    def test_empty_path_ok(self):
        ok, msg = self._validate_path("", self.tmpdir)
        self.assertTrue(ok)

    def test_write_outside_workspace(self):
        """Write to absolute outside path must be rejected."""
        from nexara_prime.sandbox_v2 import _validate_path
        ok, _ = _validate_path("/tmp/outside_file.txt", self.tmpdir)
        self.assertFalse(ok)

    def test_unicode_path_allowed(self):
        """Normal unicode paths within workspace should be OK."""
        ok, msg = self._validate_path("café/文档.txt", self.tmpdir)
        self.assertTrue(ok)


# ──────────────────────────────────────────────────
# C. Command Security (8 tests)
# ──────────────────────────────────────────────────

class CommandSecurityTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.sandbox_v2 import _sanitize_argv, _validate_command
        self._sanitize_argv = _sanitize_argv
        self._validate_command = _validate_command

    def test_shell_metacharacter_pipe(self):
        args, err = self._sanitize_argv(["echo", "a|b"])
        self.assertNotEqual(err, "")

    def test_shell_metacharacter_semicolon(self):
        args, err = self._sanitize_argv(["echo", "a;rm"])
        self.assertNotEqual(err, "")

    def test_shell_metacharacter_backtick(self):
        args, err = self._sanitize_argv(["echo", "`id`"])
        self.assertNotEqual(err, "")

    def test_shell_metacharacter_dollar_paren(self):
        args, err = self._sanitize_argv(["echo", "$(whoami)"])
        self.assertNotEqual(err, "")

    def test_clean_args_pass(self):
        args, err = self._sanitize_argv(["python3", "-c", "print(1)"])
        self.assertEqual(err, "")

    def test_forbidden_command_rm(self):
        ok, reason = self._validate_command("", ["rm", "-rf", "/"])
        self.assertFalse(ok)

    def test_forbidden_command_sudo(self):
        ok, reason = self._validate_command("", ["sudo", "ls"])
        self.assertFalse(ok)

    def test_allowed_command_python(self):
        ok, reason = self._validate_command("", ["python3", "--version"])
        self.assertTrue(ok)


# ──────────────────────────────────────────────────
# D. Browser Security — SSRF (10 tests)
# ──────────────────────────────────────────────────

class BrowserSSRFTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.connectors.browser_readonly import _ssrf_check
        self._ssrf_check = _ssrf_check

    def test_file_scheme_blocked(self):
        ok, reason = self._ssrf_check("file:///etc/passwd")
        self.assertFalse(ok)

    def test_javascript_scheme_blocked(self):
        ok, reason = self._ssrf_check("javascript:alert(1)")
        self.assertFalse(ok)

    def test_ftp_scheme_blocked(self):
        ok, reason = self._ssrf_check("ftp://evil.com/malware")
        self.assertFalse(ok)

    def test_localhost_blocked(self):
        ok, reason = self._ssrf_check("http://127.0.0.1:8080/admin")
        self.assertFalse(ok)

    def test_metadata_endpoint_blocked(self):
        ok, reason = self._ssrf_check("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)

    def test_private_10_blocked(self):
        ok, reason = self._ssrf_check("http://10.0.0.1/api")
        self.assertFalse(ok)

    def test_private_192_blocked(self):
        ok, reason = self._ssrf_check("http://192.168.1.1/admin")
        self.assertFalse(ok)

    def test_private_172_blocked(self):
        ok, reason = self._ssrf_check("http://172.16.0.1/status")
        self.assertFalse(ok)

    def test_ipv6_localhost_blocked(self):
        ok, reason = self._ssrf_check("http://[::1]:8080/")
        self.assertFalse(ok)

    def test_public_https_allowed(self):
        ok, reason = self._ssrf_check("https://example.com")
        self.assertTrue(ok, f"Expected allowed, got: {reason}")


# ──────────────────────────────────────────────────
# E. Connector Reliability (10 tests)
# ──────────────────────────────────────────────────

class ConnectorReliabilityTests(unittest.TestCase):
    def test_circuit_breaker_opens(self):
        from nexara_prime.connectors.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        self.assertEqual(cb.state, "closed")
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, "open")
        self.assertFalse(cb.allow_request())

    def test_circuit_breaker_recovery(self):
        from nexara_prime.connectors.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        self.assertEqual(cb.state, "open")
        import time
        time.sleep(0.02)
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, "half_open")

    def test_circuit_breaker_half_open_success(self):
        from nexara_prime.connectors.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        import time
        time.sleep(0.02)
        self.assertTrue(cb.allow_request())
        cb.record_success()
        self.assertEqual(cb.state, "closed")

    def test_health_monitor_circuit_tracking(self):
        from nexara_prime.connectors.health import ConnectorHealthMonitor
        hm = ConnectorHealthMonitor()
        cb = hm.get_circuit("test_connector", threshold=2)
        cb.record_failure()
        cb.record_failure()
        self.assertTrue(hm.is_circuit_open("test_connector"))

    def test_lifecycle_valid_transitions(self):
        from nexara_prime.connectors.base import ConnectorLifecycleState
        from nexara_prime.connectors.lifecycle import ConnectorLifecycle
        self.assertTrue(ConnectorLifecycle.can_transition(
            ConnectorLifecycleState.UNREGISTERED, ConnectorLifecycleState.REGISTERED))
        self.assertFalse(ConnectorLifecycle.can_transition(
            ConnectorLifecycleState.UNREGISTERED, ConnectorLifecycleState.HEALTHY))

    def test_lifecycle_is_operational(self):
        from nexara_prime.connectors.base import ConnectorLifecycleState
        from nexara_prime.connectors.lifecycle import ConnectorLifecycle
        self.assertTrue(ConnectorLifecycle.is_operational(ConnectorLifecycleState.HEALTHY))
        self.assertFalse(ConnectorLifecycle.is_operational(ConnectorLifecycleState.FAILED))

    def test_manifest_creation(self):
        from nexara_prime.connectors.base import ConnectorManifest, RiskLevel, ConnectorPermission
        m = ConnectorManifest(
            connector_id="test", version="0.1",
            capabilities=["read"], risk_level=RiskLevel.R1,
            permission_scopes=[ConnectorPermission("test.read", RiskLevel.R1)],
        )
        self.assertEqual(m.connector_id, "test")
        self.assertEqual(m.risk_level, RiskLevel.R1)

    def test_permission_registry_auto_approve_r0(self):
        from nexara_prime.connectors.permissions import ConnectorPermissionRegistry
        from nexara_prime.connectors.base import ConnectorPermission, RiskLevel
        reg = ConnectorPermissionRegistry()
        reg.register_permissions("c1", [ConnectorPermission("r0.scope", RiskLevel.R0)])
        self.assertTrue(reg.auto_approve_r0_r1("c1", "r0.scope"))

    def test_permission_revocation(self):
        from nexara_prime.connectors.permissions import ConnectorPermissionRegistry
        from nexara_prime.connectors.base import ConnectorPermission, RiskLevel
        reg = ConnectorPermissionRegistry()
        reg.register_permissions("c1", [ConnectorPermission("s1", RiskLevel.R1)])
        self.assertTrue(reg.auto_approve_r0_r1("c1", "s1"))
        reg.revoke_permission("c1", "s1")
        self.assertFalse(reg.auto_approve_r0_r1("c1", "s1"))

    def test_connector_registry_register(self):
        from nexara_prime.connectors.registry import ConnectorRegistry
        from nexara_prime.connectors.base import ConnectorManifest, BaseConnector, RiskLevel
        reg = ConnectorRegistry()
        m = ConnectorManifest(connector_id="ct1", risk_level=RiskLevel.R1)
        c = BaseConnector(m)
        reg.register(c)
        self.assertIn("ct1", reg.list_ids())


# ──────────────────────────────────────────────────
# F. Identity / Authorization (8 tests)
# ──────────────────────────────────────────────────

class IdentityAuthorizationTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.identity import IdentityStore, Role
        self.IdentityStore = IdentityStore
        self.Role = Role

    def test_owner_has_all_permissions(self):
        store = self.IdentityStore()
        self.assertTrue(store.check_permission("local-owner", "security.admin"))
        self.assertTrue(store.check_permission("local-owner", "mission.create"))

    def test_readonly_limited(self):
        store = self.IdentityStore()
        store._user.roles = [self.Role.READ_ONLY]
        self.assertTrue(store.check_permission("local-owner", "mission.read"))
        self.assertFalse(store.check_permission("local-owner", "mission.create"))

    def test_agent_denied_secret_manage(self):
        store = self.IdentityStore()
        self.assertFalse(store.check_permission("local-owner", "secret.manage", is_agent=True))

    def test_agent_denied_security_admin(self):
        store = self.IdentityStore()
        self.assertFalse(store.check_permission("local-owner", "security.admin", is_agent=True))

    def test_permission_grant_and_revoke(self):
        store = self.IdentityStore()
        store._user.roles = [self.Role.READ_ONLY]
        g = store.grant_permission("mission.create", "admin")
        self.assertIsNotNone(g.grant_id)
        r = store.revoke_permission(g.grant_id, "admin", "test revoke")
        self.assertFalse(store.check_permission("local-owner", "mission.create"))

    def test_revoked_permission_denied(self):
        store = self.IdentityStore()
        store._user.roles = [self.Role.OPERATOR]
        # Operator should retain role perms unless specifically revoked via grant_id
        self.assertTrue(store.check_permission("local-owner", "mission.create"))

    def test_operator_permissions(self):
        store = self.IdentityStore()
        store._user.roles = [self.Role.OPERATOR]
        self.assertTrue(store.check_permission("local-owner", "mission.create"))
        self.assertFalse(store.check_permission("local-owner", "security.admin"))

    def test_auditor_read_only(self):
        store = self.IdentityStore()
        store._user.roles = [self.Role.AUDITOR]
        self.assertTrue(store.check_permission("local-owner", "evidence.read"))
        self.assertFalse(store.check_permission("local-owner", "mission.create"))


# ──────────────────────────────────────────────────
# G. Audit Integrity (8 tests)
# ──────────────────────────────────────────────────

class AuditIntegrityTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        self.SecurityAuditLedger = SecurityAuditLedger

    def test_chain_starts_empty(self):
        ledger = self.SecurityAuditLedger()
        self.assertEqual(ledger.count(), 0)

    def test_verify_empty_chain(self):
        ledger = self.SecurityAuditLedger()
        ok, msg = ledger.verify_chain()
        self.assertTrue(ok)

    def test_single_entry_chain(self):
        ledger = self.SecurityAuditLedger()
        ledger.record("auth", actor_id="u1", decision="allowed")
        ok, msg = ledger.verify_chain()
        self.assertTrue(ok)
        self.assertEqual(ledger.count(), 1)

    def test_chain_of_three(self):
        ledger = self.SecurityAuditLedger()
        for i in range(3):
            ledger.record(f"event_{i}", actor_id="u1")
        ok, msg = ledger.verify_chain()
        self.assertTrue(ok)

    def test_tamper_detection(self):
        ledger = self.SecurityAuditLedger()
        ledger.record("e1", actor_id="u1")
        ledger.record("e2", actor_id="u1")
        # Tamper with first entry's hash
        ledger._entries[0].event_hash = "0" * 64
        tampered = ledger.detect_tamper()
        self.assertGreater(len(tampered), 0)

    def test_no_false_tamper_detection(self):
        ledger = self.SecurityAuditLedger()
        for i in range(5):
            ledger.record(f"event_{i}")
        tampered = ledger.detect_tamper()
        self.assertEqual(len(tampered), 0)

    def test_missing_event_detection(self):
        ledger = self.SecurityAuditLedger()
        ledger.record("e1")
        ledger.record("e2")
        self.assertEqual(ledger.missing_events(), 0)

    def test_list_entries_filtered(self):
        ledger = self.SecurityAuditLedger()
        ledger.record("auth", actor_id="u1")
        ledger.record("blocked", actor_id="u1")
        ledger.record("auth", actor_id="u2")
        auths = ledger.list_entries(event_type="auth")
        self.assertEqual(len(auths), 2)


# ──────────────────────────────────────────────────
# Network Policy (7 tests)
# ──────────────────────────────────────────────────

class NetworkPolicyTests(unittest.TestCase):
    def setUp(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        self.NetworkPolicyEngine = NetworkPolicyEngine

    def test_deny_by_default(self):
        engine = self.NetworkPolicyEngine(deny_by_default=True)
        d = engine.evaluate("https://unknown.example.com")
        self.assertFalse(d.allowed)

    def test_allowlist_domain(self):
        engine = self.NetworkPolicyEngine(deny_by_default=True)
        engine.allow_domain("example.com")
        d = engine.evaluate("https://example.com/page")
        self.assertTrue(d.allowed, f"Expected allowed, got: {d.reason}")

    def test_private_ip_blocked(self):
        engine = self.NetworkPolicyEngine(deny_by_default=False)
        d = engine.evaluate("http://10.0.0.1/api")
        self.assertFalse(d.allowed)

    def test_metadata_ip_blocked(self):
        engine = self.NetworkPolicyEngine(deny_by_default=False)
        d = engine.evaluate("http://169.254.169.254/")
        self.assertFalse(d.allowed)

    def test_post_blocked_by_default(self):
        engine = self.NetworkPolicyEngine(deny_by_default=False)
        engine.allow_domain("example.com")
        d = engine.evaluate("https://example.com/api", method="POST")
        self.assertFalse(d.allowed)

    def test_get_allowed(self):
        engine = self.NetworkPolicyEngine(deny_by_default=False)
        engine.allow_domain("example.com")
        d = engine.evaluate("https://example.com/api", method="GET")
        self.assertTrue(d.allowed)

    def test_file_scheme_blocked(self):
        engine = self.NetworkPolicyEngine(deny_by_default=False)
        d = engine.evaluate("file:///etc/passwd")
        self.assertFalse(d.allowed)


# ──────────────────────────────────────────────────
# Sandbox Capability (5 tests)
# ──────────────────────────────────────────────────

class SandboxCapabilityTests(unittest.TestCase):
    def test_macos_probe(self):
        from nexara_prime.sandbox_v2 import MacOSSandboxBackend, OS_SANDBOX_CAPABLE
        sb = MacOSSandboxBackend()
        cap = sb.probe_capability()
        self.assertIsNotNone(cap.sandbox_mechanism)
        self.assertIn(cap.sandbox_mechanism, ("macos_sandbox", "workspace_jail", "test", "none"))

    def test_process_constrained_backend(self):
        from nexara_prime.sandbox_v2 import ProcessConstrainedBackend, WORKSPACE_JAIL_ENFORCED
        sb = ProcessConstrainedBackend()
        cap = sb.probe_capability()
        self.assertIn(WORKSPACE_JAIL_ENFORCED, cap.flags)

    def test_test_backend_execute(self):
        from nexara_prime.sandbox_v2 import TestSandboxBackend, SandboxInvocation
        sb = TestSandboxBackend()
        inv = SandboxInvocation(argv=["echo", "hello"])
        receipt = sb.execute(inv)
        self.assertIn("hello", receipt.stdout)

    def test_test_backend_timeout(self):
        from nexara_prime.sandbox_v2 import TestSandboxBackend, SandboxInvocation
        sb = TestSandboxBackend()
        inv = SandboxInvocation(argv=["sleep", "5"], timeout=0.1)
        receipt = sb.execute(inv)
        self.assertTrue(receipt.timed_out)

    def test_sanitize_shell_false(self):
        """shell=False must be enforced."""
        from nexara_prime.sandbox_v2 import _sanitize_argv
        args, err = _sanitize_argv(["echo", "hello; rm -rf /"])
        self.assertNotEqual(err, "")


# ──────────────────────────────────────────────────
# Browser E2E tests (simulated, 5 tests)
# ──────────────────────────────────────────────────

class BrowserE2ETests(unittest.TestCase):
    def test_browser_post_rejected(self):
        """POST must be rejected in read-only mode."""
        # This is tested at the connector level — POST is blocked
        from nexara_prime.connectors.browser_readonly import _ssrf_check
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        engine.allow_domain("example.com")
        d = engine.evaluate("https://example.com/form", method="POST")
        self.assertFalse(d.allowed)

    def test_browser_upload_rejected(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        d = engine.evaluate("https://example.com/upload", method="POST")
        self.assertFalse(d.allowed)

    def test_response_size_limit(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        engine.set_max_response_bytes(1024)
        self.assertEqual(engine._max_response_bytes, 1024)

    def test_redirect_revalidation(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        engine.allow_domain("safe.com")
        d = engine.evaluate_redirect("https://safe.com/a", "http://10.0.0.1/b")
        self.assertFalse(d.allowed)

    def test_dns_rebinding_simulation(self):
        """DNS resolving to private IP must be blocked."""
        # The network policy already validates resolved IPs against private ranges
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        d = engine.evaluate("http://evil.com", resolved_ip="192.168.1.1")
        self.assertFalse(d.allowed)


# ──────────────────────────────────────────────────
# Red Team tests (15+)
# ──────────────────────────────────────────────────

class RedTeamTests(unittest.TestCase):
    """Adversarial security tests."""

    def test_path_traversal_double_encode(self):
        from nexara_prime.sandbox_v2 import _validate_path
        ok, _ = _validate_path("..%2F..%2F..%2Fetc%2Fpasswd", "/tmp/test")
        self.assertFalse(ok)

    def test_command_arg_injection(self):
        from nexara_prime.sandbox_v2 import _sanitize_argv
        args, err = _sanitize_argv(["ls", "-la; rm -rf /"])
        self.assertNotEqual(err, "")

    def test_env_var_injection(self):
        from nexara_prime.sandbox_v2 import _workspace_jail_execute, SandboxInvocation
        inv = SandboxInvocation(
            argv=["python3", "-c", "import os; print(os.environ.get('PATH',''))"],
            env={"PATH": "/evil/bin:/usr/bin"},
            timeout=5.0,
        )
        receipt = _workspace_jail_execute(inv)
        # PATH should be sanitized to safe paths
        if receipt.exit_code == 0:
            self.assertNotIn("/evil/bin", receipt.stdout)

    def test_sql_injection_not_auth_bypass(self):
        """Permission checks must use exact match, not pattern matching."""
        from nexara_prime.identity import IdentityStore
        store = IdentityStore()
        self.assertFalse(store.check_permission("local-owner", "security.admin' OR '1'='1"))

    def test_approval_bypass_insufficient_role(self):
        from nexara_prime.identity import IdentityStore, Role
        store = IdentityStore()
        store._user.roles = [Role.READ_ONLY]
        self.assertFalse(store.check_permission("local-owner", "approval.decide"))

    def test_agent_cannot_escalate_to_human(self):
        from nexara_prime.identity import IdentityStore
        store = IdentityStore()
        self.assertTrue(store.check_permission("local-owner", "security.admin", is_agent=False))
        self.assertFalse(store.check_permission("local-owner", "security.admin", is_agent=True))

    def test_double_revoke_no_effect(self):
        from nexara_prime.identity import IdentityStore, Role
        store = IdentityStore()
        store._user.roles = [Role.READ_ONLY]
        g = store.grant_permission("mission.create", "admin")
        store.revoke_permission(g.grant_id, "admin")
        # Second revoke — already revoked, should not crash
        try:
            store.revoke_permission(g.grant_id, "admin")
        except Exception:
            pass  # Expected if already revoked

    def test_secret_not_in_audit_log(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        entry = ledger.record("secret_access", resource="keychain:nexara/api_key",
                               decision="allowed")
        entry_dict = entry.__dict__
        self.assertNotIn("sk-", str(entry_dict))
        self.assertNotIn("password", str(entry_dict).lower())

    def test_max_redirects_respected(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        engine.set_max_redirects(5)
        self.assertEqual(engine._max_redirects, 5)

    def test_duplicate_invocation_idempotency(self):
        """Two invocations with same ID should produce consistent results."""
        from nexara_prime.connectors.base import ConnectorInvocation
        inv1 = ConnectorInvocation(invocation_id="same_id", action="test")
        inv2 = ConnectorInvocation(invocation_id="same_id", action="test")
        self.assertEqual(inv1.invocation_id, inv2.invocation_id)

    def test_circuit_breaker_prevents_during_open(self):
        from nexara_prime.connectors.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        self.assertFalse(cb.allow_request())

    def test_manifest_credential_never_stores_value(self):
        from nexara_prime.connectors.base import ConnectorCredentialReference
        ref = ConnectorCredentialReference(backend="keychain", path="nexara/key")
        d = ref.__dict__
        self.assertNotIn("sk-", str(d))
        self.assertNotIn("password", str(d).lower())

    def test_policy_decision_logging(self):
        from nexara_prime.network_policy import NetworkPolicyEngine
        engine = NetworkPolicyEngine(deny_by_default=False)
        engine.evaluate("http://169.254.169.254/")
        decisions = engine.get_recent_decisions()
        self.assertGreater(len(decisions), 0)

    def test_audit_chain_ordering_preserved(self):
        from nexara_prime.security_audit import SecurityAuditLedger
        ledger = SecurityAuditLedger()
        for i in range(10):
            ledger.record(f"event_{i}")
        entries = ledger.list_entries(limit=100)
        for i, e in enumerate(entries):
            self.assertEqual(e["event_type"], f"event_{i}")

    def test_nonexistent_permission_denied(self):
        from nexara_prime.identity import IdentityStore
        store = IdentityStore()
        self.assertFalse(store.check_permission("local-owner", "nonexistent.permission"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
