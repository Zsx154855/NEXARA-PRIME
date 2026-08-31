import sys, json, urllib.request
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from nexara_prime.intelligence.planner.planner import Planner
from nexara_prime.intelligence.planner.contracts import GoalStatus
from nexara_prime.intelligence.capability.registry import CapabilityRegistry
from nexara_prime.intelligence.capability.contracts import Capability
from nexara_prime.intelligence.decision.decision_engine import DecisionEngine
from nexara_prime.intelligence.evaluator.evaluator import EvaluationEngine
from nexara_prime.intelligence.reflection.reflection_loop import ReflectionLoop
from nexara_prime.intelligence.council.council import AgentCouncil

BASE = "http://127.0.0.1:8765"

# 1. User input → Goal
p = Planner(BASE)
goal = p.understand("检查运行时健康并生成简报")
goal.status = GoalStatus.ANALYZED
print("GOAL:", goal.id, goal.status.value)

# 2. Goal → Plan → TaskGraph
plan = p.decompose(goal)
graph = p.build_graph(plan)
goal.status = GoalStatus.PLANNED
print("PLAN:", plan.id, "steps:", len(plan.steps), "graph:", len(graph.nodes))

# 3. Capability match
reg = CapabilityRegistry()
reg.register(Capability(name="health_check", description="检查运行状态", tools=["run"]))
cap = reg.match(goal.objective)
print("CAPABILITY:", cap.name if cap else None)

# 4. Decision
decision = DecisionEngine().decide(goal.objective, ["run", "skip"], {})
print("DECISION:", decision.selected_action, "confidence:", decision.confidence, "reason:", decision.reason_code)

# 5. Mission (真实 Runtime)
mission = p.to_mission(goal)
mid = mission["mission_id"]
p.plan_mission(mid)
req = urllib.request.Request(
    f"{BASE}/api/missions/{mid}/approve",
    data=json.dumps({"approved": True, "actor": "human", "note": "v12-loop"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
urllib.request.urlopen(req, timeout=120)
run = p.run_mission(mid)
final_state = run.get("current_state")
goal.status = GoalStatus.COMPLETED if final_state == "Completed" else GoalStatus.FAILED
print("MISSION:", mid, final_state, "| goal_status:", goal.status.value)

# 6. Evaluation
ev = EvaluationEngine().evaluate({"current_state": final_state, "evidence_count": 16})
print("EVALUATION: success:", ev.success_score, "quality:", ev.quality_score, "recommendation:", ev.recommendation)

# 7. Reflection
ref = ReflectionLoop().reflect(ev)
print("REFLECTION:", ref.insight, "| policy:", ref.memory_update_policy)

# 8. Council
c = AgentCouncil(); c.add_default_agents()
print("COUNCIL pipeline:", c.pipeline())
print("COUNCIL governance:", c.governance())

print("GOAL_ID:", goal.id)
print("MISSION_ID:", mid)
print("=== PRODUCT LOOP COMPLETE ===")
