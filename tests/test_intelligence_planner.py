"""Tests for intelligence.planner — contracts + Planner orchestration."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.planner.contracts import (
    Goal,
    GoalStatus,
    Plan,
    PlanStep,
    TaskGraph,
    TaskNode,
)
from nexara_prime.intelligence.planner.planner import Planner


class TestGoalStatus:
    def test_six_states(self):
        assert len(GoalStatus) == 6

    def test_lifecycle_order(self):
        names = [s.name for s in GoalStatus]
        assert names == ["CREATED", "ANALYZED", "PLANNED", "EXECUTING", "COMPLETED", "FAILED"]


class TestGoal:
    def test_defaults(self):
        g = Goal()
        assert g.id.startswith("goal_")
        assert g.status is GoalStatus.CREATED
        assert g.priority == 3
        assert g.constraints == []

    def test_custom_fields(self):
        g = Goal(user_intent="fix bug", objective="fix bug", priority=5)
        assert g.user_intent == "fix bug"
        assert g.priority == 5


class TestPlanStep:
    def test_defaults(self):
        s = PlanStep()
        assert s.id.startswith("step_")
        assert s.kind == "tool"
        assert s.dependencies == []
        assert s.estimated_cost == 0.0


class TestPlan:
    def test_defaults(self):
        p = Plan()
        assert p.id.startswith("plan_")
        assert p.risk == "low"
        assert p.steps == []


class TestTaskGraph:
    def test_empty_graph(self):
        tg = TaskGraph()
        assert tg.as_adjacency() == {}

    def test_as_adjacency(self):
        n1 = TaskNode(id="a", dependencies=[])
        n2 = TaskNode(id="b", dependencies=["a"])
        tg = TaskGraph(goal_id="g1", nodes=[n1, n2])
        adj = tg.as_adjacency()
        assert adj == {"a": [], "b": ["a"]}

    def test_as_adjacency_returns_copy(self):
        n = TaskNode(id="x", dependencies=["y"])
        tg = TaskGraph(nodes=[n])
        adj = tg.as_adjacency()
        adj["x"].append("z")
        assert tg.as_adjacency()["x"] == ["y"]


class TestPlanner:
    def test_understand(self):
        p = Planner()
        goal = p.understand("deploy service")
        assert goal.user_intent == "deploy service"
        assert goal.objective == "deploy service"
        assert len(goal.success_criteria) == 1

    def test_decompose_produces_three_steps(self):
        p = Planner()
        goal = p.understand("test")
        plan = p.decompose(goal)
        assert plan.goal_id == goal.id
        assert len(plan.steps) == 3
        assert plan.steps[0].kind == "agent"
        assert plan.steps[1].kind == "tool"
        assert plan.steps[2].kind == "verification"

    def test_decompose_chain_dependencies(self):
        p = Planner()
        goal = p.understand("test")
        plan = p.decompose(goal)
        s1, s2, s3 = plan.steps
        assert s1.dependencies == []
        assert s2.dependencies == [s1.id]
        assert s3.dependencies == [s2.id]

    def test_build_graph(self):
        p = Planner()
        goal = p.understand("test")
        plan = p.decompose(goal)
        graph = p.build_graph(plan)
        assert graph.goal_id == plan.goal_id
        assert len(graph.nodes) == 3
        adj = graph.as_adjacency()
        assert len(adj) == 3

    def test_base_url_strip_trailing_slash(self):
        p = Planner(base_url="http://localhost:9999/")
        assert p.base_url == "http://localhost:9999"
