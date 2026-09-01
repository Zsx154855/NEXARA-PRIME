"""Tests for intelligence.planner — contracts + Planner orchestration."""
from __future__ import annotations

import json

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

    def test_task_node_defaults(self):
        n = TaskNode(id="t1")
        assert n.name == ""
        assert n.kind == "tool"
        assert n.dependencies == []

    def test_goal_custom_fields(self):
        g = Goal(
            user_intent="deploy",
            objective="deploy service",
            deadline="2026-12-31",
            constraints=["no downtime"],
            success_criteria=["service live"],
        )
        assert g.deadline == "2026-12-31"
        assert g.constraints == ["no downtime"]
        assert g.success_criteria == ["service live"]

    def test_plan_estimated_fields(self):
        p = Plan(estimated_cost=1.5, estimated_time=300)
        assert p.estimated_cost == 1.5
        assert p.estimated_time == 300

    def test_understand_empty_string(self):
        p = Planner()
        goal = p.understand("")
        assert goal.user_intent == ""
        assert goal.objective == ""
        assert goal.success_criteria == ["完成: "]


class TestPlannerHTTPBridge:
    def _mock_urlopen(self, response_data):
        import io
        from unittest.mock import MagicMock, patch

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return patch("urllib.request.urlopen", return_value=mock_resp)

    def test_to_mission(self):
        import json as json_mod
        p = Planner(base_url="http://test:8765")
        with self._mock_urlopen({"mission_id": "m1", "current_state": "Created"}) as mock_url:
            result = p.to_mission(Goal(objective="deploy"))
            assert result["mission_id"] == "m1"
            call_args = mock_url.call_args
            req = call_args[0][0]
            assert req.full_url == "http://test:8765/api/missions"
            body = json_mod.loads(req.data.decode())
            assert body["objective"] == "deploy"

    def test_plan_mission(self):
        import json as json_mod
        p = Planner()
        with self._mock_urlopen({"mission_id": "m1", "plan": []}) as mock_url:
            result = p.plan_mission("m1")
            req = mock_url.call_args[0][0]
            assert req.full_url == "http://127.0.0.1:8765/api/missions/m1/plan"
            assert req.data is None

    def test_run_mission(self):
        p = Planner()
        with self._mock_urlopen({"mission_id": "m1", "current_state": "Completed"}):
            result = p.run_mission("m1")
            assert result["current_state"] == "Completed"

    def test_plan_and_execute(self):
        import json as json_mod
        p = Planner()
        with self._mock_urlopen({"mission_id": "m42", "current_state": "Created"}) as mock_url:
            result = p.plan_and_execute("fix bug")
            assert result["mission_id"] == "m42"
            assert result["step_count"] == 3
            assert result["graph_nodes"] == 3
            assert result["mission_state"] == "Created"
