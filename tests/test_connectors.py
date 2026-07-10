"""Tests for connector support modules: registry, lifecycle, permissions, health, audit.
Matches current connectors/* API — rewritten to align with unified implementation.
Replaces subagent-generated version (SHA256: 75392af1...)."""
from __future__ import annotations

import time
import unittest

from nexara_prime.connectors.base import (
    BaseConnector, ConnectorHealth, ConnectorLifecycleState,
    ConnectorManifest, ConnectorPermission,
)
from nexara_prime.connectors.registry import ConnectorRegistry
from nexara_prime.connectors.lifecycle import ConnectorLifecycle
from nexara_prime.connectors.permissions import ConnectorPermissionRegistry
from nexara_prime.connectors.health import CircuitBreaker, ConnectorHealthMonitor
from nexara_prime.connectors.audit import AuditEvent, ConnectorAuditTrail
from nexara_prime.models import RiskLevel


def _make_manifest(connector_id: str = "test_conn") -> ConnectorManifest:
    return ConnectorManifest(
        connector_id=connector_id, version="1.0",
        capabilities=["read", "write"],
        permission_scopes=[ConnectorPermission("fs.read", RiskLevel.R1)],
    )


class _MinimalConn(BaseConnector):
    pass


# ── Registry Tests ──

class TestConnectorRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ConnectorRegistry()
        self.manifest = _make_manifest()
        self.conn = _MinimalConn(self.manifest)

    def test_register_adds_connector(self):
        self.reg.register(self.conn)
        self.assertIn("test_conn", self.reg.list_ids())

    def test_register_twice_raises(self):
        self.reg.register(self.conn)
        with self.assertRaises(ValueError):
            self.reg.register(_MinimalConn(self.manifest))

    def test_unregister_removes(self):
        self.reg.register(self.conn)
        self.reg.unregister("test_conn")
        self.assertNotIn("test_conn", self.reg.list_ids())

    def test_unregister_missing_raises(self):
        with self.assertRaises(KeyError):
            self.reg.unregister("nope")

    def test_get_returns_connector(self):
        self.reg.register(self.conn)
        self.assertIs(self.reg.get("test_conn"), self.conn)

    def test_get_missing_raises(self):
        with self.assertRaises(KeyError):
            self.reg.get("nope")

    def test_list_connectors(self):
        self.reg.register(self.conn)
        self.reg.register(_MinimalConn(_make_manifest("conn_b")))
        self.assertEqual(len(self.reg.list_connectors()), 2)
        self.assertEqual(len(self.reg.list_ids()), 2)

    def test_get_manifest(self):
        self.reg.register(self.conn)
        m = self.reg.get_manifest("test_conn")
        self.assertEqual(m.connector_id, "test_conn")

    def test_get_manifest_missing_raises(self):
        with self.assertRaises(KeyError):
            self.reg.get_manifest("nope")

    def test_register_triggers_connector_register(self):
        self.assertEqual(self.conn.state, ConnectorLifecycleState.UNREGISTERED)
        self.reg.register(self.conn)
        self.assertEqual(self.conn.state, ConnectorLifecycleState.REGISTERED)


# ── Lifecycle Tests ──

class TestConnectorLifecycle(unittest.TestCase):
    S = ConnectorLifecycleState

    def test_can_transition_valid(self):
        self.assertTrue(ConnectorLifecycle.can_transition(self.S.UNREGISTERED, self.S.REGISTERED))
        self.assertTrue(ConnectorLifecycle.can_transition(self.S.HEALTHY, self.S.DEGRADED))
        self.assertTrue(ConnectorLifecycle.can_transition(self.S.CIRCUIT_OPEN, self.S.HEALTHY))
        self.assertTrue(ConnectorLifecycle.can_transition(self.S.STOPPED, self.S.STARTING))

    def test_can_transition_invalid(self):
        self.assertFalse(ConnectorLifecycle.can_transition(self.S.UNREGISTERED, self.S.STOPPED))
        self.assertFalse(ConnectorLifecycle.can_transition(self.S.HEALTHY, self.S.UNREGISTERED))

    def test_validate_transition_valid_passes(self):
        conn = _MinimalConn(_make_manifest())
        conn._state = self.S.UNREGISTERED
        ConnectorLifecycle.validate_transition(conn, self.S.REGISTERED)

    def test_validate_transition_invalid_raises(self):
        conn = _MinimalConn(_make_manifest())
        conn._state = self.S.UNREGISTERED
        with self.assertRaises(ValueError):
            ConnectorLifecycle.validate_transition(conn, self.S.STOPPED)

    def test_is_operational(self):
        self.assertTrue(ConnectorLifecycle.is_operational(self.S.HEALTHY))
        self.assertTrue(ConnectorLifecycle.is_operational(self.S.DEGRADED))
        self.assertFalse(ConnectorLifecycle.is_operational(self.S.STOPPED))
        self.assertFalse(ConnectorLifecycle.is_operational(self.S.UNREGISTERED))

    def test_is_terminal(self):
        self.assertTrue(ConnectorLifecycle.is_terminal(self.S.STOPPED))
        self.assertTrue(ConnectorLifecycle.is_terminal(self.S.FAILED))
        self.assertFalse(ConnectorLifecycle.is_terminal(self.S.HEALTHY))


# ── Permissions Tests ──

class TestConnectorPermissionRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ConnectorPermissionRegistry()

    def test_register_and_get(self):
        self.reg.register_permissions("c1", [ConnectorPermission("fs.read", RiskLevel.R1)])
        p = self.reg.get_permission("c1", "fs.read")
        self.assertIsNotNone(p)
        self.assertEqual(p.scope, "fs.read")

    def test_get_permission_missing(self):
        self.assertIsNone(self.reg.get_permission("nope", "x"))

    def test_revoke_permission(self):
        self.reg.register_permissions("c1", [ConnectorPermission("fs.write", RiskLevel.R1)])
        self.reg.revoke_permission("c1", "fs.write")
        self.assertTrue(self.reg.is_revoked("c1", "fs.write"))

    def test_revoke_missing_noop(self):
        self.reg.revoke_permission("c1", "ghost")
        self.assertTrue(self.reg.is_revoked("c1", "ghost"))

    def test_list_permissions(self):
        self.reg.register_permissions("c1", [
            ConnectorPermission("a", RiskLevel.R0),
            ConnectorPermission("b", RiskLevel.R1),
        ])
        perms = self.reg.list_permissions("c1")
        self.assertEqual(len(perms), 2)

    def test_list_permissions_empty(self):
        self.assertEqual(len(self.reg.list_permissions("c1")), 0)

    def test_auto_approve_r0(self):
        self.reg.register_permissions("c1", [ConnectorPermission("r", RiskLevel.R0)])
        self.assertTrue(self.reg.auto_approve_r0_r1("c1", "r"))

    def test_auto_approve_r1_revoked(self):
        self.reg.register_permissions("c1", [ConnectorPermission("r", RiskLevel.R1)])
        self.reg.revoke_permission("c1", "r")
        self.assertFalse(self.reg.auto_approve_r0_r1("c1", "r"))

    def test_auto_approve_r2_fails(self):
        self.reg.register_permissions("c1", [ConnectorPermission("r", RiskLevel.R2)])
        self.assertFalse(self.reg.auto_approve_r0_r1("c1", "r"))

    def test_auto_approve_unknown(self):
        self.assertFalse(self.reg.auto_approve_r0_r1("nope", "x"))


# ── Circuit Breaker Tests ──

class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.cb = CircuitBreaker(failure_threshold=3, recovery_timeout=3600)

    def test_initial_state_closed(self):
        self.assertEqual(self.cb.state, "closed")

    def test_allow_request_when_closed(self):
        self.assertTrue(self.cb.allow_request())

    def test_failure_threshold_opens_circuit(self):
        for _ in range(3):
            self.cb.record_failure()
        self.assertEqual(self.cb.state, "open")

    def test_record_success_resets(self):
        self.cb.record_failure()
        self.cb.record_failure()
        self.cb.record_success()
        self.assertEqual(self.cb.failure_count, 0)
        self.assertEqual(self.cb.state, "closed")

    def test_allow_request_when_open_denies(self):
        for _ in range(3):
            self.cb.record_failure()
        self.assertFalse(self.cb.allow_request())

    def test_recovery_timeout_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        self.assertEqual(cb.state, "open")
        time.sleep(0.02)
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, "half_open")

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_success()
        self.assertEqual(cb.state, "closed")

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_failure()
        self.assertEqual(cb.state, "open")


class TestConnectorHealthMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = ConnectorHealthMonitor()

    def test_get_circuit_creates_new(self):
        cb = self.monitor.get_circuit("c1")
        self.assertEqual(cb.state, "closed")

    def test_get_circuit_returns_same(self):
        cb1 = self.monitor.get_circuit("c1")
        cb2 = self.monitor.get_circuit("c1")
        self.assertIs(cb1, cb2)

    def test_circuit_state_unknown_closed(self):
        self.assertEqual(self.monitor.circuit_state("nope"), "closed")

    def test_is_circuit_open_false_closed(self):
        self.assertFalse(self.monitor.is_circuit_open("c1"))

    def test_is_circuit_open_true_open(self):
        cb = self.monitor.get_circuit("c1")
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        self.assertTrue(self.monitor.is_circuit_open("c1"))


# ── Audit Tests ──

class TestAuditEvent(unittest.TestCase):
    def test_defaults(self):
        event = AuditEvent()
        self.assertTrue(event.audit_event_id.startswith("aud_"))
        self.assertEqual(event.actor_type, "")

    def test_round_trip(self):
        event = AuditEvent(
            event_type="connector_start", connector_id="c1",
            action="start", decision="allowed",
            actor_id="agent_1", trace_id="trace_1",
        )
        self.assertEqual(event.event_type, "connector_start")
        self.assertEqual(event.connector_id, "c1")


class TestConnectorAuditTrail(unittest.TestCase):
    def setUp(self):
        self.trail = ConnectorAuditTrail()

    def test_record(self):
        self.trail.record(AuditEvent(event_type="start", connector_id="c1"))
        self.assertEqual(len(self.trail.list_events()), 1)

    def test_list_events_all(self):
        self.trail.record(AuditEvent(event_type="a", connector_id="c1"))
        self.trail.record(AuditEvent(event_type="b", connector_id="c2"))
        self.assertEqual(len(self.trail.list_events()), 2)

    def test_list_events_filtered(self):
        self.trail.record(AuditEvent(event_type="a", connector_id="c1"))
        self.trail.record(AuditEvent(event_type="b", connector_id="c2"))
        events = self.trail.list_events(connector_id="c1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "a")

    def test_list_events_limit(self):
        for i in range(10):
            self.trail.record(AuditEvent(event_type=str(i), connector_id="c1"))
        events = self.trail.list_events(connector_id="c1", limit=3)
        self.assertEqual(len(events), 3)

    def test_flush_clears(self):
        self.trail.record(AuditEvent(event_type="x"))
        self.trail.flush()
        self.assertEqual(len(self.trail.list_events()), 0)


if __name__ == "__main__":
    unittest.main()
