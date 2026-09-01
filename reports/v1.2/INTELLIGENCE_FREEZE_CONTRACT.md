# NEXARA V1.2 INTELLIGENCE LAYER — FREEZE CONTRACT

状态: V1.2 DEVELOPMENT START, PHASE 0
继承: V1.1_GOLDEN_BASELINE = IMMUTABLE (V1.1 SEALED)

## 1. Intelligence Boundary (边界)

V1.2 = Intelligence Layer Overlay, 建立在 V1.1 之上, 不修改 V1.1 Runtime。

禁止修改:
- Session Layer (session*.py)
- Mission Runtime (runtime.py)
- Recovery Engine (recovery*.py + error_taxonomy)
- Memory OS (memory*.py)
- Token Governor (cost_governor.py)
- Control Plane (control_plane.py)
- Upgrade/Rollback (upgrade_manager.py)
- SQLite 已有 semantics
- 已有接口/evidence/baseline

原则: V1.2 决策 → V1.1 执行 (不是 V1.2 重新执行)

## 2. 核心架构

User → INTELLIGENCE LAYER (Planner | Reasoner | Evaluator) → Agent Decision Engine → V1.1 Operating Layer (Session/Mission/Execution/Recovery/Evidence/Memory)

## 3. Object Map (V1.2 新增对象, L2/L3 只读复用 V1.1)

| 对象 | 字段 | 归属 Phase |
|------|------|-----------|
| Goal | id/user_intent/objective/constraints/success_criteria/priority/deadline | P1 |
| Plan | id/goal_id/steps/dependencies/risk/estimated_cost/estimated_time | P1 |
| TaskGraph | Goal→Task(A→Tool/B→Agent/C→Verification) | P1 |
| Decision | input/context/available_actions/selected_action/confidence/reason_code | P2 |
| ReasoningMode | NORMAL/FAST/DEEP/RECOVERY/COST_OPTIMIZED | P2 |
| Capability | id/name/description/inputs/outputs/required_tools/cost/risk/permissions/success_rate | P3 |
| Evaluation | mission_id/quality_score/cost_score/success_score/failure_count/recovery_count/recommendation | P4 |
| Reflection | experience→evaluation→reflection→memory_update→future_decision | P5 |

## 4. V1.1 Impact Analysis (影响分析)

V1.2 对 V1.1 的影响 = ZERO (纯只读复用 V1.1 的 Session/Mission/Memory/Evidence)。

- 不修改 V1.1 任何文件 (src_mod 保持 6, src_new 保持 11)
- 不修改 SQLite schema (schema_version 保持 1)
- 不修改 Provider/Governance/Mission semantics
- 不修改 launchd/rollback
- V1.2 新增对象全部为独立 L2/L3 模块 (intelligence/ 目录)

## 5. 决策隐私边界 (Reasoning Layer)

禁止保存: 私密 Chain of Thought
允许保存: 可审计决策摘要 / 规则依据 / 选择结果 (Decision.reason_code)

## 6. 禁止 (Reflection Loop)

禁止: self_modify_runtime (不自动修改自身代码)
允许: 优化 Prompt / Policy / Strategy / Memory

## 7. 硬门

V1.1_DRIFT = 0
CORE_RUNTIME_DRIFT = 0
P0 = 0, P1 = 0, P2 = 0

## 8. Token Governance (V1.2 增量)

继承 V1.1 Token Governor。
新增 Intelligence Budget: Reasoning Budget / Planning Budget / Reflection Budget (避免智能层无限消耗)。

## PHASE 0 验收

INTELLIGENCE_BOUNDARY = PASS (边界已建立, V1.1_DRIFT=0)
V1.1_DRIFT = 0 (已验证: HEAD 3e073188, src_mod=6, src_new=11 未变)
