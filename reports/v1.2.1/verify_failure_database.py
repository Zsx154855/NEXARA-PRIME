import sys, json
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from nexara_prime.intelligence.failure_database import FailureDatabase, FailureRecord, FailureCategory

db = FailureDatabase()
db.record(FailureRecord(
    category=FailureCategory.TOOL,
    context="mission_2ae64ccf6948 report-write tool 重放",
    trigger="background_execution + 手动 run 竞争, report-write 幂等键命中但 arguments 不同",
    root_cause="tools.py _existing() 对 arguments 不匹配抛 tool_idempotency_conflict, 无 graceful reuse",
    recovery_action="tools.py 修复: 生成式 tool 幂等复用 (reuse_existing)",
    final_result="已修复, 后续 mission 全部 Completed",
    lesson="生成式 tool 幂等判断应复用已有结果而非冲突",
))
db.record(FailureRecord(
    category=FailureCategory.EXECUTION,
    context="mission_fc8e2687fa1d DecisionOutput 处理",
    trigger="DecisionOutput 对象访问 estimated_tokens 属性",
    root_cause="'DecisionOutput' object has no attribute 'estimated_tokens' (代码缺陷)",
    recovery_action="定位 DecisionOutput 定义, 补属性或改用正确字段",
    final_result="Failed (待修复)",
    lesson="访问对象属性前需确认属性存在",
))
print("failure_count:", db.count())
print("categories:", db.categories_present())
out = "/Volumes/NEXARA/NEXARA-PRIME/reports/v1.2.1/failure_database.json"
json.dump(db.to_dicts(), open(out, "w"), ensure_ascii=False, indent=2)
print("saved:", out)
