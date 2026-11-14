"""M4 A→B transfer experiment tests (deterministic, real SQLite, no provider calls)."""

from __future__ import annotations

import json

from nexara_prime.experience_transfer import (
    ExperienceTransferExperiment,
    run_experiment,
    write_result,
)


class TestTransferExperiment:
    def test_learned_experience_improves_unseen_task(self, tmp_path):
        result = run_experiment(tmp_path)
        assert result["cold_start"]["success_rate"] == 0.0
        assert result["experienced"]["success_rate"] == 1.0
        assert result["delta_success_rate"] == 1.0
        assert result["experienced"]["influenced_decisions"] == 6
        assert result["cost"]["model_calls"] == 0
        assert result["cost"]["network_calls"] == 0

    def test_revocation_removes_the_effect(self, tmp_path):
        result = run_experiment(tmp_path)
        assert result["revocation"] == {"revoked": 6, "of": 6}
        assert result["after_revocation"]["success_rate"] == 0.0
        assert result["after_revocation"]["influenced_decisions"] == 0
        assert result["revocation_effective"] is True

    def test_no_training_means_no_gain(self, tmp_path):
        result = run_experiment(tmp_path, train=False)
        assert result["cold_start"]["success_rate"] == result["experienced"]["success_rate"] == 0.0
        assert result["delta_success_rate"] == 0.0
        assert result["cost"]["model_calls"] == 0

    def test_reversed_evidence_does_not_help_the_default_policy(self, tmp_path):
        experiment = ExperienceTransferExperiment(tmp_path, profile="default_succeeds")
        try:
            result = experiment.run()
        finally:
            experiment.close()
        assert {*result["cold_start"]["actions"]} == {"claude_adapter"}
        assert {*result["experienced"]["actions"]} == {"claude_adapter"}
        assert result["delta_success_rate"] == 0.0

    def test_revoked_experiences_are_not_recalled(self, tmp_path):
        experiment = ExperienceTransferExperiment(tmp_path)
        try:
            experiment.record_training()
            assert experiment.learner.rank_experiences("invoice adapter")
            experiment.revoke()
            assert experiment.learner.rank_experiences("invoice adapter") == []
        finally:
            experiment.close()

    def test_result_is_deterministic_and_writable(self, tmp_path):
        first = run_experiment(tmp_path / "one")
        second = run_experiment(tmp_path / "two")
        keys = ("cold_start", "experienced", "delta_success_rate", "after_revocation")
        assert {key: first[key] for key in keys} == {key: second[key] for key in keys}

        target = tmp_path / "result.json"
        write_result(first, target)
        assert json.loads(target.read_text())["delta_success_rate"] == 1.0

    def test_experience_can_hurt_under_distribution_shift(self, tmp_path):
        experiment = ExperienceTransferExperiment(
            tmp_path, task_b_environment="default_ok"
        )
        try:
            result = experiment.run()
        finally:
            experiment.close()
        assert result["cold_start"]["success_rate"] == 1.0
        assert result["experienced"]["success_rate"] == 0.0
        assert result["delta_success_rate"] == -1.0
        assert result["revocation_effective"] is True
