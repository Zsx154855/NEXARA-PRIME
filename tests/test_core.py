from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from nexara_prime.api import create_app
from nexara_prime.capabilities import CapabilityRegistry
from nexara_prime.config import Settings
from nexara_prime.models import MemoryKind, MissionState
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.scheduler import AdaptiveScheduler
from nexara_prime.token_compiler import TokenCompiler


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.reports = self.root / "reports"
        self.settings = Settings(self.root / "runtime" / "nexara.db", self.workspace, self.reports, "mock", True, "127.0.0.1", 8765)
        self.runtime = NexaraRuntime(self.settings)

    def tearDown(self):
        self.runtime.store.close()
        self.tmp.cleanup()

    def test_event_bus_persists_and_replays(self):
        seen = []
        self.runtime.events.subscribe(seen.append)
        event = self.runtime.events.publish("test.event", "aggregate", "test", "tester", "trace_test", {"ok": True})
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.runtime.events.replay("aggregate")[0]["event_type"], "test.event")
        self.assertEqual(event.payload["ok"], True)

    def test_evidence_memory_and_writer_lease(self):
        evidence = self.runtime.evidence.add("mission_1", "test", "Test", "payload", "trace_1")
        self.assertEqual(len(evidence.sha256), 64)
        memory = self.runtime.memory.write(MemoryKind.FACT, "fact", "value", "trace_1", "mission_1", evidence.evidence_id)
        self.assertEqual(self.runtime.memory.inspect("mission_1")[0]["memory_id"], memory.memory_id)
        lease = self.runtime.leases.acquire("resource", "writer_a", "trace_1")
        with self.assertRaises(RuntimeError):
            self.runtime.leases.acquire("resource", "writer_b", "trace_2")
        self.runtime.leases.release(lease.lease_id, "writer_a", "trace_1")

    def test_scheduler_and_token_compiler_are_dynamic(self):
        spec = self.runtime.compiler.compile("Analyze the local project materials and generate a report", str(self.workspace))
        assignments = AdaptiveScheduler(CapabilityRegistry()).schedule(spec)
        personas = {a.persona.value for a in assignments}
        self.assertIn("Nexara", personas)
        self.assertIn("Nyx", personas)
        self.assertIn("Vertex", personas)
        compiled = TokenCompiler().compile(spec, ["tool.file_read"], ["MissionSpec"], [], "bounded context")
        self.assertLess(compiled.estimated_tokens, 500)
        self.assertIn("Mission", compiled.task)

    def test_full_acceptance_flow(self):
        source = self.workspace / "sample-project"
        source.mkdir(parents=True)
        (source / "README.md").write_text("local source material", encoding="utf-8")
        mission = self.runtime.create_mission("Read the local project materials and generate a verified report", str(source))
        planned = self.runtime.plan_mission(mission.mission_id)
        self.assertEqual(planned.state, MissionState.APPROVAL.value)
        self.assertIsNotNone(planned.pending_approval_id)
        approved = self.runtime.approve_mission(mission.mission_id)
        self.assertEqual(approved.state, MissionState.EXECUTION.value)
        completed = self.runtime.run_mission(mission.mission_id)
        self.assertEqual(completed.state, MissionState.COMPLETED.value)
        self.assertTrue(Path(completed.result["report_path"]).exists())
        self.assertTrue(completed.result["evaluation_passed"])
        self.assertGreaterEqual(len(self.runtime.evidence.list(mission.mission_id)), 10)
        self.assertTrue(any(item["event_type"] == "mission.state_changed" for item in self.runtime.store.list_events(mission.mission_id)))
        self.assertTrue(self.runtime.memory.inspect(mission.mission_id))
        self.assertTrue(self.runtime.evaluator.list(mission.mission_id))

    def test_api_and_cli_smoke(self):
        app = create_app(self.runtime)
        client = TestClient(app)
        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        created = client.post("/api/missions", json={"objective": "Read local notes"})
        self.assertEqual(created.status_code, 200)
        mission_id = created.json()["mission_id"]
        status = client.get(f"/api/missions/{mission_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["mission_id"], mission_id)

        from nexara_prime.cli import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["runtime-status"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "ok")


if __name__ == "__main__":
    unittest.main()
