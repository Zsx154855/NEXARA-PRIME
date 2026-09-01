import sys, json, urllib.request
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from nexara_prime.intelligence.planner.planner import Planner

BASE = "http://127.0.0.1:8765"
p = Planner(BASE)

# 1. understand
goal = p.understand("检查运行时健康并生成简报")
print("Goal:", goal.id, "| objective:", goal.objective[:30], "| criteria:", len(goal.success_criteria))

# 2. decompose
plan = p.decompose(goal)
print("Plan:", plan.id, "| steps:", len(plan.steps), "| deps:", [s.dependencies for s in plan.steps])

# 3. graph
graph = p.build_graph(plan)
print("TaskGraph nodes:", len(graph.nodes), "| goal_id match:", graph.goal_id == goal.id)

# 4. to_mission (真实 V1.1 API)
mission = p.to_mission(goal)
mid = mission.get("mission_id")
print("Mission:", mid, "| state:", mission.get("current_state"))

# 5. plan → approve → run (真实 Runtime)
p.plan_mission(mid)
req = urllib.request.Request(
    f"{BASE}/api/missions/{mid}/approve",
    data=json.dumps({"approved": True, "actor": "human", "note": "planner-v12"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
urllib.request.urlopen(req, timeout=120)
run = p.run_mission(mid)
print("Mission run:", run.get("current_state"))

# 6. 最终状态
req2 = urllib.request.Request(f"{BASE}/api/missions/{mid}")
final = json.loads(urllib.request.urlopen(req2, timeout=30).read())
print("FINAL:", final.get("current_state"), "| evidence:", final.get("evidence_count"))
print("GOAL_ID:", goal.id)
print("MISSION_ID:", mid)
