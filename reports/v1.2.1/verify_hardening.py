import sys
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from nexara_prime.intelligence.planner.planner import Planner
from nexara_prime.intelligence.decision.decision_engine import DecisionEngine
from nexara_prime.intelligence.capability.registry import CapabilityRegistry
from nexara_prime.intelligence.capability.contracts import Capability
from nexara_prime.intelligence.evaluator.evaluator import EvaluationEngine
from nexara_prime.intelligence.reflection.reflection_loop import ReflectionLoop

# 1. Planner 边界
p = Planner()
g1 = p.understand("")
print("planner_empty_ok:", g1.objective == "")
g2 = p.understand("多步骤任务：先检查系统状态，再生成报告，最后验证结果")
plan = p.decompose(g2)
print("planner_complex_steps:", len(plan.steps), "deps_chain:", [s.dependencies for s in plan.steps])

# 2. Decision 边界
de = DecisionEngine()
d1 = de.decide("goal", [], {})
print("decision_empty_actions:", d1.selected_action, "conf:", d1.confidence)
d2 = de.decide("goal", ["a", "b"], {"forced_action": "b"})
print("decision_policy_binding:", d2.selected_action, d2.reason_code)

# 3. Capability 边界
r = CapabilityRegistry()
print("capability_no_match:", r.match("xyz") is None)
r.register(Capability(name="health_check", description="检查运行状态", tools=["run"]))
print("capability_unrelated_fallback:", r.match("完全无关的任务xyz") is None)

# 4. Evaluation 边界 (缺失数据 + 失败)
ee = EvaluationEngine()
e1 = ee.evaluate({})
print("evaluation_missing_data:", e1.success_score, e1.quality_score)
e2 = ee.evaluate({"current_state": "Failed", "evidence_count": 3})
print("evaluation_failed:", e2.success_score, "failure_count:", e2.failure_count, "recommendation:", e2.recommendation)

# 5. Reflection 边界
rl = ReflectionLoop()
r2 = rl.reflect(e2)
print("reflection_failed:", r2.insight, r2.memory_update_policy)
print("reflection_no_runtime_mutation:", not hasattr(rl, "mutate_runtime"))

print("=== HARDENING BOUNDARY CHECKS COMPLETE ===")
