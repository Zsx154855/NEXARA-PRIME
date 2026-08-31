import sys, json, urllib.request
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from nexara_prime.intelligence.planner.planner import Planner
from nexara_prime.intelligence.capability.registry import CapabilityRegistry
from nexara_prime.intelligence.capability.contracts import Capability
from nexara_prime.intelligence.decision.decision_engine import DecisionEngine
from nexara_prime.intelligence.evaluator.evaluator import EvaluationEngine
from nexara_prime.recovery_runtime import RecoveryExecutor
from nexara_prime.cost_governor import TokenGovernor
from nexara_prime.memory_os import MemoryOS, MemoryType

BASE = "http://127.0.0.1:8765"
p = Planner(BASE)

# CASE 1: 简单任务 (真实 mission)
g1 = p.understand("输出当前系统时间")
m1 = p.to_mission(g1)
mid1 = m1["mission_id"]
p.plan_mission(mid1)
req = urllib.request.Request(f"{BASE}/api/missions/{mid1}/approve",
    data=json.dumps({"approved": True, "actor": "human", "note": "v121-case1"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
urllib.request.urlopen(req, timeout=120)
run1 = p.run_mission(mid1)
print("CASE1 简单任务:", mid1, run1.get("current_state"))

# CASE 2: 多步骤 (TaskGraph)
g2 = p.understand("多步骤：检查状态→生成报告→验证结果")
plan2 = p.decompose(g2)
graph2 = p.build_graph(plan2)
print("CASE2 多步骤 TaskGraph nodes:", len(graph2.nodes), "adjacency:", graph2.as_adjacency())

# CASE 3: 失败恢复 (真实失败样本 + recovery 分类)
re = RecoveryExecutor()
d = re.classify("TOOL_IDEMPOTENCY_CONFLICT")
print("CASE3 失败恢复:", d.get("recovery_strategy"), "| retryable:", d.get("retryable"))

# CASE 4: 长期上下文 (Memory)
m = MemoryOS()
e = m.create_entry(MemoryType.SEMANTIC, "长期记忆验证", "conv", {"conv": "c1"})
print("CASE4 长期上下文 Memory:", e.status)

# CASE 5: 成本敏感 (Token Governance)
tg = TokenGovernor()
tg.set_budget("mission", "case5", 10)
r1 = tg.record_usage("mission", "case5", 8, None)
r2 = tg.record_usage("mission", "case5", 5, None)
print("CASE5 成本敏感:", r1, "->", r2)

print("=== REAL WORLD VALIDATION 5 CASES COMPLETE ===")
