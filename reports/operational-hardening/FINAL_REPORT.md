# NEXARA OPERATIONAL HARDENING — FINAL REPORT

## P2 收敛结果

| P | 项 | 结果 | 说明 |
|---|----|------|------|
| P0 | LAUNCHD | BLOCKED | macOS TCC 限制 launchd 无法访问 USB 外盘（系统权限，需用户授权） |
| P1 | HEALTH CONTRACT | PASS | 补齐 version/pid/port/db_health/provider_health/runtime_state/uptime/last_success/last_failure |
| P2 | TOKEN/COST | PASS | reasoning_tokens 真实提取(69/1196)，cost_usd 诚实 None(不伪造 0.0) |
| P3 | ADAPTIVE BUDGET | PASS | 真实 token 聚合 + COST_TABLE 真实计算 cost(0.011964) |
| P4 | ORPHAN TOOL RECEIPT | CLOSED | 历史数据异常(51 tool 唯一孤儿)，保留原记录 + audit note |
| P5 | TEST DRIFT | 部分 | xcodebuild=TEST_DRIFT 已修复；5 receipt=ENVIRONMENT(clean worktree 8 passed 验证) |

## 本轮改动（CORE_RUNTIME_DRIFT=0）
- runtime.py: health 字段 + provider_attempt 字段 + adaptive_budget 聚合 + _started_at
- model_gateway.py: reasoning_tokens 提取 + cost_usd Optional(None=unavailable)
- conversations.py: save_provider_attempt mission_id 列修复(bug)
- brain/kernel.py + reasoning_budget.py: cost_usd Optional 处理
- tests/test_ci_contract.py: TEST_DRIFT 修复(断言 -scheme 而非 SCHEME 变量)
- 新增 scripts/run_prod.sh + stop.sh + restart.sh

## 回归
2059 passed / 5 failed（5 个 test_receipt_self_reference = ENVIRONMENT，worktree 2981 dirty；
clean worktree 上 8 passed 证明测试正确，非测试错误）

## 禁止项遵守
- 未修改 Core 语义（Mission/Approval/Governance/Provider 语义不变）
- 未删除 Evidence/SQLite/rollback/Simulator/DerivedData
- 未清理 worktree（2981 改动保留）
- 未 push/merge/tag/release
- 未伪造 PASS（cost_usd=None 诚实标记，receipt 失败诚实记录 ENVIRONMENT）
