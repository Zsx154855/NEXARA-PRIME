# PHASE 2-4 TOOL_IDEMPOTENCY_CONFLICT 修复

## 根因 (forensic)
mission_2ae64ccf6948 状态机回退:
  ... → Evaluation → Completed (rowid 2267)
  Execution → Failed (rowid 2279)  ← background 重放导致回退

链: conversation auto 创建 mission (background_execution=true) → approval 后
background worker 自动执行到 Completed → 手动 POST /run 触发第二次执行 →
report-write 幂等键(mission:report-write)命中已有 invocation, 但 arguments
(report content 含动态时间戳)不同 → tools.py:82 抛 tool_idempotency_conflict
→ mission 从 Execution 回退 Failed.

## 修复 (minimal patch, L1 tools.py)
tools.py `_existing()`: 原逻辑 mission_id/tool_name/arguments 任一不匹配即 conflict.
改为: mission_id + tool_name 不匹配才 conflict (真冲突);
arguments 不匹配时, 若 tool 为生成式 (file_write_report/write_workspace_file)
则 reuse 已有结果 (replay-safe); 查询式 tool (file_read/read_file) 保持严格幂等.

## 验证
- test_chief_brain_closure_v1.py: 43 passed (含 replay + conflict 测试)
- 完整回归: 2059 passed, 5 ENVIRONMENT (与修复前一致, 无新回归)
- 真实 mission: mission_73c4eb1f8b5f Completed (evidence=16, receipt=present, eval=passed, provider=deepseek)
- 修复前失败场景 (conversation auto + run): 不再返回 tool_idempotency_conflict

## 判定
PRODUCT_LOOP 核心缺口已关闭. CORE_RUNTIME_DRIFT 仍=0 (只改 tools.py 幂等判断, 未动 Core Mission/Approval/Governance semantics).
