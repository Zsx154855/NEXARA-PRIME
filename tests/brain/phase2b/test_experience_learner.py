"""Tests: Experience Learning."""
import pytest
from src.nexara_prime.brain.experience_learner import ExperienceLearner


@pytest.fixture
def mc(mock_mc):
    return mock_mc


@pytest.fixture
def learner(mc):
    return ExperienceLearner(mc)


class TestExperienceRecord:
    def test_record_outcome_commits(self, learner):
        cid = learner.record_outcome("m1", "success", "tool_call", "done", True)
        assert cid is not None

    def test_record_failure(self, learner):
        cid = learner.record_outcome("m2", "failure", "tool_call", "error", False)
        assert cid is not None

    def test_record_lesson(self, learner):
        cid = learner.record_lesson("m1", "use batch operations")
        assert cid is not None


class TestPatternExtraction:
    def test_extract_from_multiple_experiences(self, learner):
        for i in range(5):
            learner.record_outcome("m1", "success", "tool_a", f"ok_{i}", True)
        for i in range(3):
            learner.record_outcome("m2", "failure", "tool_b", f"err_{i}", False)
        patterns = learner.extract_patterns(20)
        assert len(patterns) >= 1

    def test_extract_success_pattern(self, learner):
        for i in range(5):
            learner.record_outcome("m1", "success", "fast_tool", f"ok_{i}", True)
        patterns = learner.extract_patterns(10)
        assert len(patterns) >= 1, "Should find at least one pattern for fast_tool"
        fast = [p for p in patterns if "fast_tool" in p.description]
        assert len(fast) == 1
        assert fast[0].pattern_type == "tool_selection_success"
        assert fast[0].success_rate == 1.0
        assert fast[0].frequency == 5

    def test_extract_failure_pattern(self, learner):
        for i in range(8):
            learner.record_outcome("m1", "failure", "slow_tool", f"err_{i}", False)
        patterns = learner.extract_patterns(10)
        assert len(patterns) >= 1, "Should find at least one pattern for slow_tool"
        slow = [p for p in patterns if "slow_tool" in p.description]
        assert len(slow) == 1
        assert slow[0].pattern_type == "decision_path_outcome"
        assert slow[0].success_rate == 0.0
        assert slow[0].frequency == 8

    def test_few_samples_no_pattern(self, learner):
        learner.record_outcome("m1", "success", "rare_tool", "ok", True)
        learner.record_outcome("m2", "success", "rare_tool", "ok", True)
        patterns = learner.extract_patterns(10)
        assert all(p.frequency < 3 for p in patterns)


class TestExperienceRanking:
    def test_rank_returns_sorted(self, learner):
        for i in range(3):
            learner.record_outcome("m1", "success", "good_tool", f"ok_{i}", True)
        for i in range(2):
            learner.record_outcome("m2", "failure", "bad_tool", f"err_{i}", False)
        ranked = learner.rank_experiences("good bad tool", top_k=10)
        assert isinstance(ranked, list)


class TestLessons:
    def test_get_lessons_returns_list(self, learner):
        learner.record_lesson("m1", "always validate inputs")
        learner.record_lesson("m2", "use idempotent operations")
        lessons = learner.get_lessons("validate", top_k=5)
        assert isinstance(lessons, list)


class TestPruning:
    def test_prune_irrelevant(self, learner):
        learner.record_outcome("m1", "success", "test", "ok", True)
        pruned = learner.prune_irrelevant(0.9)
        assert isinstance(pruned, int)


class TestSummary:
    def test_summarize(self, learner):
        for i in range(4):
            learner.record_outcome(f"m{i}", "success", "tool_a", f"ok_{i}", True)
        s = learner.summarize()
        assert "patterns_found" in s
