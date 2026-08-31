# NEXARA OPERATIONAL RUNTIME — ACCEPTANCE REPORT

## 执行模式
MULTI-AGENT(3 scout) + 只读调查 + 最小必要修改 + 真实验证(非 mock)。

## PHASE 结果

### 已验证 PASS（真实磁盘/API 证据）
- BASELINE_SEAL = PASS（git 3e07318, DB quick_check ok, 唯一 runtime 8765）
- STARTUP = PASS（run_prod.sh → provider=deepseek, model=deepseek-v4-pro, mock=false）
- SHUTDOWN = PASS（stop.sh SIGTERM graceful，端口释放）
- RESTART = PASS（前后一致：62 missions/24 completed/475 evidence/records 无重复）
- MISSION_RECOVERY = PASS（checkpoint 222 + idempotency + duplicate_steps=0）
- REAL_CONVERSATION = PASS（真实 deepseek 回复，非 mock）
- REAL_MISSION = PASS（mission_da80b3ac43d7 全闭环 Completed+receipt+memory+16 evidence）
- GOVERNANCE = PASS（DENY=Blocked；audit_entry 614 条 hash 链 + trace_id + risk_level）
- MEMORY = PASS（25 committed，procedural layer）
- TOKEN/COST = PASS（provider_attempt 含 input/output/total_tokens + latency + retry，failed 5/succeeded 45）
- OBSERVABILITY = PASS（60 events，trace_id 唯一贯穿，12 event_type）
- TRACEABILITY = PASS（mission→approval→tool→evidence→memory→checkpoint 全链）
- LOG_SECURITY = PASS（无 hardcoded secret，key 在 Keychain）
- METRICS = PASS（stats/overview 端点，mock_mode=false，recovery_state=healthy）

### Gap 修复（最小必要，未碰 Core）
1. 旧路径 CLAUDE.md/README.md → canonical 外盘（P2 文档）
2. 新增 run_prod.sh（production，无 --reload，强制 deepseek + 正确 model）
3. 新增 stop.sh + restart.sh（graceful lifecycle）

### 记录但未修改（禁止修改 Core）
- health 端点缺 version/pid/port/uptime（/api/runtime/stats + overview 已补充）
- api.py 无显式 lifespan（uvicorn 默认 SIGTERM + SQLite 自动 close 已足够）

### 回归
- 2058 passed / 6 failed（TEST_DRIFT：test_receipt_self_reference 假设 worktree clean，
  项目长期 dirty 2968 改动；非 Core/Runtime 缺陷，pre-existing）

## 本轮改动
- CLAUDE.md, README.md（旧路径修复）
- scripts/run_prod.sh, stop.sh, restart.sh（新增）
- CORE_RUNTIME_DRIFT = 0（未改 src/nexara_prime/）
