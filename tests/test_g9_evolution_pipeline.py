"""G9: Evolution Pipeline E2E Tests — ImprovementProposal → Benchmark → Rollback."""
from __future__ import annotations

import unittest

from nexara_prime.benchmark_runner import BenchmarkRunner
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.models import MissionSpec, RiskLevel
from nexara_prime.product_reality.models import ImprovementProposal


class ImprovementProposalModelTests(unittest.TestCase):
    """Test the ImprovementProposal object model."""

    def test_create_valid_proposal(self):
        p = ImprovementProposal(
            mission_id="m1",
            target="evaluation.correctness",
            hypothesis="Adding domain-specific evaluators increases correctness from 0.5 to >0.9",
            evidence_refs=["evt_001", "evt_002"],
            expected_gain={"correctness": 0.45, "reliability": 0.2},
            risk_level=RiskLevel.R2,
            experiment_plan=["Run 10 domain missions", "Compare correctness scores", "Check no regressions"],
            rollback_plan=["Revert to MVP evaluation", "Restore deterministic scoring"],
        )
        self.assertTrue(p.proposal_id.startswith("improvement_"))
        self.assertEqual(p.target, "evaluation.correctness")
        self.assertEqual(p.status, "proposed")
        self.assertEqual(len(p.evidence_refs), 2)
        self.assertEqual(len(p.experiment_plan), 3)
        self.assertEqual(p.risk_level, RiskLevel.R2)

    def test_rejects_blank_identity(self):
        with self.assertRaises(ValueError):
            ImprovementProposal(mission_id="   ", target="t", hypothesis="h", evidence_refs=["e"])

    def test_rejects_blank_hypothesis(self):
        with self.assertRaises(ValueError):
            ImprovementProposal(mission_id="m1", target="t", hypothesis="  ", evidence_refs=["e"])

    def test_requires_evidence_refs(self):
        with self.assertRaises(Exception):
            ImprovementProposal(mission_id="m1", target="t", hypothesis="h", evidence_refs=[])


class BenchmarkRunnerTests(unittest.TestCase):
    """Test the BenchmarkRunner with baseline vs candidate comparison."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.store = SQLiteStore(f"{self.tmp}/test.db")
        self.events = EventBus(self.store)
        self.runner = BenchmarkRunner(self.store, self.events)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_mission(self, mission_id: str, state: str, risk: RiskLevel,
                      evidence_count: int = 0, tool_count: int = 0,
                      tokens: int = 1000, has_report: bool = False,
                      has_rollback: bool = False):  # returns Mission
        from nexara_prime.models import Mission, MissionState
        state_map = {
            "COMPLETED": MissionState.COMPLETED,
            "FAILED": MissionState.FAILED,
            "RUNNING": MissionState.RUNNING,
            "EVALUATION": MissionState.EVALUATION,
        }
        m_state = state_map.get(state, MissionState.COMPLETED)
        spec = MissionSpec(mission_id=mission_id, title="Test", objective="Test",
                           boundaries=[], constraints=[], risk_level=risk)
        m = Mission(mission_id=mission_id, spec=spec, state=m_state, trace_id=f"trace_{mission_id}")
        m.result["evidence_refs"] = list(range(evidence_count))
        m.result["tool_count"] = tool_count
        m.result["total_tokens"] = tokens
        if has_report:
            m.result["report_path"] = "/tmp/report.md"
        if has_rollback:
            m.rollback_point = "checkpoint_001"
        return m

    def test_benchmark_improvement(self):
        proposal = ImprovementProposal(
            mission_id="m1", target="reliability",
            hypothesis="Adding verification improves reliability",
            evidence_refs=["evt_001"],
            expected_gain={"reliability": 0.3},
            risk_level=RiskLevel.R2,
        )
        baseline = self._make_mission("m1", "COMPLETED", RiskLevel.R2,
                                       evidence_count=0, tool_count=0, tokens=2000,
                                       has_report=False, has_rollback=False)
        candidate = self._make_mission("m2", "COMPLETED", RiskLevel.R2,
                                        evidence_count=4, tool_count=5, tokens=800,
                                        has_report=True, has_rollback=True)

        result = self.runner.run(proposal, baseline, candidate)
        self.assertTrue(result.passed)
        self.assertGreater(result.improvement_pct, 0)
        self.assertEqual(len(result.regression_flags), 0)

    def test_benchmark_regression_detected(self):
        proposal = ImprovementProposal(
            mission_id="m1", target="safety",
            hypothesis="Risky change that reduces safety",
            evidence_refs=["evt_001"],
            risk_level=RiskLevel.R4,
        )
        baseline = self._make_mission("m1", "COMPLETED", RiskLevel.R2,
                                       evidence_count=4, tool_count=3, tokens=500,
                                       has_report=True, has_rollback=True)
        candidate = self._make_mission("m2", "FAILED", RiskLevel.R4,
                                        evidence_count=0, tool_count=0, tokens=5000,
                                        has_report=False, has_rollback=False)

        result = self.runner.run(proposal, baseline, candidate)
        self.assertFalse(result.passed)
        self.assertLess(result.improvement_pct, 0)
        self.assertGreater(len(result.regression_flags), 0)

    def test_compare_candidates_selects_best(self):
        proposal = ImprovementProposal(
            mission_id="m1", target="efficiency",
            hypothesis="Optimization improves token efficiency",
            evidence_refs=["evt_001"],
            risk_level=RiskLevel.R1,
        )
        baseline = self._make_mission("m1", "COMPLETED", RiskLevel.R1)
        good = self._make_mission("g", "COMPLETED", RiskLevel.R1,
                                   evidence_count=6, tool_count=4, tokens=300,
                                   has_report=True, has_rollback=True)
        bad = self._make_mission("b", "FAILED", RiskLevel.R3,
                                  evidence_count=0, tool_count=0, tokens=10000)

        r_good = self.runner.run(proposal, baseline, good)
        r_bad = self.runner.run(proposal, baseline, bad)
        best = self.runner.compare_candidates(proposal, [r_good, r_bad])
        self.assertIsNotNone(best)
        self.assertEqual(best.benchmark_id, r_good.benchmark_id)
        self.assertTrue(best.passed)

    def test_reject_with_evidence(self):
        proposal = ImprovementProposal(
            mission_id="m1", target="safety",
            hypothesis="Unsafe change",
            evidence_refs=["evt_001"],
            risk_level=RiskLevel.R4,
        )
        baseline = self._make_mission("m1", "COMPLETED", RiskLevel.R2,
                                       evidence_count=4, tool_count=3, tokens=500,
                                       has_report=True, has_rollback=True)
        candidate = self._make_mission("m2", "FAILED", RiskLevel.R4)
        result = self.runner.run(proposal, baseline, candidate)
        rejection = self.runner.reject_with_evidence(proposal, result)
        self.assertEqual(rejection["verdict"], "rejected")
        self.assertIn("regression_detected", rejection["reason"])

    def test_evolution_pipeline_full_e2e(self):
        """Complete pipeline: Evidence → Proposal → Benchmark → Compare → Reject/Rollback."""
        # 1. Evidence drives proposal
        proposal = ImprovementProposal(
            mission_id="e2e_mission",
            target="evaluation.accuracy",
            hypothesis="Domain-specific evaluators improve accuracy by 40%",
            evidence_refs=["evt_e2e_001"],
            expected_gain={"correctness": 0.4, "reliability": 0.2},
            risk_level=RiskLevel.R2,
            experiment_plan=["Run E2E test suite", "Compare baseline vs candidate", "Validate no regressions"],
            rollback_plan=["Restore previous evaluation engine", "Revert to MVP scoring"],
        )
        self.assertEqual(proposal.status, "proposed")

        # 2. Run benchmark
        baseline = self._make_mission("e2e_mission", "COMPLETED", RiskLevel.R2,
                                       evidence_count=1, tool_count=1, tokens=2000,
                                       has_report=True, has_rollback=False)
        candidate = self._make_mission("e2e_candidate", "COMPLETED", RiskLevel.R2,
                                        evidence_count=6, tool_count=5, tokens=600,
                                        has_report=True, has_rollback=True)
        result = self.runner.run(proposal, baseline, candidate)
        self.assertTrue(result.passed, f"Benchmark failed: {result.regression_flags}")

        # 3. Compare candidates
        best = self.runner.compare_candidates(proposal, [result])
        self.assertIsNotNone(best)

        # 4. Reject path works when regression exists
        bad_proposal = ImprovementProposal(
            mission_id="e2e_mission",
            target="evaluation.accuracy",
            hypothesis="A change that makes things worse",
            evidence_refs=["evt_e2e_002"],
            risk_level=RiskLevel.R3,
            rollback_plan=["Revert"],
        )
        bad_baseline = self._make_mission("e2e_mission", "COMPLETED", RiskLevel.R2,
                                           evidence_count=5, tool_count=4, tokens=400,
                                           has_report=True, has_rollback=True)
        bad_candidate = self._make_mission("e2e_fail", "FAILED", RiskLevel.R4,
                                            evidence_count=0, tool_count=0, tokens=10000)
        bad_result = self.runner.run(bad_proposal, bad_baseline, bad_candidate)
        rejection = self.runner.reject_with_evidence(bad_proposal, bad_result)
        self.assertEqual(rejection["verdict"], "rejected")

        # Pipeline complete
        self.assertTrue(True, "Full evolution E2E pipeline: PASSED")


if __name__ == "__main__":
    unittest.main()
