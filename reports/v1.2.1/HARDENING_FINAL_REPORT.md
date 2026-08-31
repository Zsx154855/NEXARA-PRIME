# NEXARA V1.2.1 HARDENING FINAL REPORT

时间: 2026-08-21 17:45 (UTC+8)
Baseline: NEXARA V1.2 INTELLIGENCE LAYER (SEALED)

## BASELINE

V1.2_BASELINE = PRESERVED (GIT_HEAD 3e073188, src_mod=6 未变)
CORE_RUNTIME_DRIFT = 0

## PHASE 判定

| Phase | 结果 | 证据 |
|-------|------|------|
| A SYSTEM_HEALTH | PASS | health报告: mission=75, evidence=650, audit=835 |
| B INTELLIGENCE_HARDENING | PASS | 边界验证 + decision_engine空actions修复 |
| C FAILURE_DATABASE | PASS | failure_database模块 + 2真实失败样本 |
| D REAL_WORLD_VALIDATION | PASS | 5 case: 简单/多步骤/失败恢复/上下文/成本 |
| E LONG_RUN_STABILITY | NOT_VERIFIED | 24H+72H cron已启动, 需真实窗口 |
| F COST_GOVERNANCE | PASS | TokenGovernor budget WARN→BLOCK |
| G OBSERVABILITY | PASS | ControlPlane 全字段统一观察 |
| H REGRESSION | PASS | 2059 passed, 5 ENVIRONMENT(非回归) |

## 发现的真实缺陷 (记录到 failure_database.json)

1. tool_idempotency_conflict (已修复: tools.py 幂等复用)
2. brain/__init__.py DecisionOutput 契约缺 estimated_tokens (kernel.py:369 访问) → 导致 mission_fc8e2687fa1d Failed — V1.1 Core bug, 需 CHANGE_CONTRACT 修复

## PHASE E 诚实状态

24H_STABILITY: cron cb3cb28fbfba (每1h×24) 已启动, 监控 health/dbsize/missions/events/rss
72H_STABILITY: cron ead269c0bf9e (每1h×72) 已启动
监控输出: reports/v1.2.1/stability_monitor.log

## Risk

P0 = 0
P1 = 0
P2 = 1 (brain DecisionOutput estimated_tokens 契约缺失, 需 CHANGE_CONTRACT)

## FINAL_DECISION

V1.2.1 = BLOCKED

ROOT_CAUSE: PHASE E 24H/72H 长期稳定性测试需真实 24-72 小时连续运行窗口, 单次会话无法完成 (禁止 FALSE PASS / 提前宣称稳定性)。

SAFE_STATE:
- 24H + 72H 稳定性监控 cron 已启动并记录 (health/dbsize/missions/events/rss)
- 其余 7 个 Phase (A/B/C/D/F/G/H) 全部 PASS, runtime 稳定运行 (pid 63990, health ok)
- V1.2 baseline preserved, CORE_RUNTIME_DRIFT=0
- 24H/72H 窗口完成后 (cron 记录齐全) 可验证 LONG_RUN_STABILITY → 重新验收 SEAL

EVIDENCE_ROOT: /Volumes/NEXARA/NEXARA-PRIME/reports/v1.2.1/
