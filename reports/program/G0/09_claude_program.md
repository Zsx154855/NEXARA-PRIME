# 09 — Claude Program (Continuous)

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

本文件是 G0 盘点完成后交付给 Claude Code 的**唯一连续执行程序**。Claude 必须按此程序从 G7 连续推进到 READY_FOR_HUMAN_APPROVAL。

---

## 9.1 Bootstrap Directive

```
你是 NEXARA PRIME Claude Program 执行器。
你的唯一任务：按本文件的 Gate 顺序，从当前 Gate 连续推进到 READY_FOR_HUMAN_APPROVAL。

执行前必须加载:
  1. NEXARA_PROGRAM_CONSTITUTION_V1.md
  2. NEXARA_DEVELOPMENT_GATES_V1.yaml
  3. .nexara/GATE_STATUS.json (after correction)
  4. 本文件 (reports/program/G0/09_claude_program.md)
```

---

## 9.2 Gate Execution Loop

```
WHILE current_gate != "READY_FOR_HUMAN_APPROVAL":
  1. 读取 GATE_STATUS.json → 确定 current_gate
  2. 验证依赖 Gate 全部 PASS (否则 BLOCKED)
  3. 执行 Gate Scope:
     a. Scope & Inputs
     b. Implementation Tasks
     c. Tests (写测试优先 — TDD)
     d. Evidence Generation (E1/E2)
     e. Gate Acceptance Report
     f. State Update (.nexara/GATE_STATUS.json)
     g. Local Commit
  4. IF gate_result == PASS:
       选择下一个依赖已满足的 Gate
     ELIF gate_result == BLOCKED:
       IF blocker == "human_approval_required":
         停止并请求人类介入
       ELIF blocker == "external_credential":
         标记 BLOCKED，跳到下一个可执行 Gate
       ELSE:
         记录阻断原因，尝试缓解
  5. IF 所有 Gate PASS 或 BLOCKED:
       终止于 READY_FOR_HUMAN_APPROVAL
```

---

## 9.3 Current Position: G7 → READY_FOR_HUMAN_APPROVAL

### G7: 三端产品体验 (Current Gate — PARTIAL → PASS)

**Scope:** 将 Web Dashboard 验收完善 + macOS/iOS 原生应用 Runtime Truth 绑定验证

**Inputs:**
- `ui/src/` — 8 screen components
- `experience/macos/` — SwiftUI app skeleton
- `experience/ios/` — SwiftUI app skeleton
- `src/nexara_prime/api.py` — 30+ REST endpoints
- `docs/05-UI-UX/UI Truth Contract.md`

**Non-goals:**
- 不重新设计 UI 视觉系统
- 不添加新功能 screen
- 不做 App Store 发布准备

**Implementation Tasks:**
1. Web Dashboard Runtime Truth verification — 验证每个 screen 显示的数据来自 API 权威状态
2. Web Dashboard screenshot evidence — 320/768/1024/1440 四个断点截图
3. macOS app Runtime Truth API binding test — 验证 RuntimeViewModel 正确绑定 API
4. iOS app iPad-adaptive layout — 验证 AdaptiveContentView 在 iPad 上使用 NavigationSplitView
5. Native build evidence — macOS .app + iOS simulator build
6. Usability acceptance checklist — 8 screens × 3 platforms
7. Gate Acceptance Report

**Tests:**
- UI Runtime Truth contract tests (pytest — API 端点验证)
- Swift build compilation test (macOS + iOS)
- Screenshot comparison (manual verification)

**Evidence Required:**
- `reports/program/G7/runtime_truth_web_screenshots/` (4 breakpoints × 8 screens)
- `reports/program/G7/native_build_evidence.md`
- `reports/program/G7/usability_acceptance.md`
- `reports/program/G7/gate_acceptance_v3.md`

---

### G8: SDK / Plugin Boundary (NOT_STARTED → PASS)

**Scope:** 完成至少一个可安装 SDK (Python 优先) + Plugin 声明 schema

**Non-goals:**
- 不实现全部 5 个 SDK
- 不实现完整插件市场

**Implementation Tasks:**
1. Python SDK — 完善 client.py (覆盖所有 API 端点) + 添加错误处理/重试 + 发布到本地
2. Plugin Declaration Schema — JSON Schema for capability plugin manifest
3. Plugin Sandbox 概念 — os-level isolation 文档 (macOS sandbox-exec 复用)
4. SDK Quick Start 文档 + 示例
5. Gate Acceptance Report

**Tests:**
- Python SDK integration tests (against running runtime)
- Plugin schema validation tests

---

### G9: Evaluation & Evolution (PARTIAL → PASS)

**Scope:** 执行 benchmark runner + 建立 candidate comparison pipeline + Evolution E2E

**Non-goals:**
- 不训练/微调模型
- 不实现完整 A/B 测试平台

**Implementation Tasks:**
1. 执行 benchmark_runner.py — 产生量化性能数据
2. Regression suite isolation — 确认回归测试覆盖关键路径
3. Candidate comparison — 至少 2 个配置变体的 A/B 对比
4. Evolution proposal → simulation → benchmark → approval E2E 最少链路
5. Gate Acceptance Report

**Tests:**
- Benchmark runner integration test
- Evolution pipeline E2E test

---

### G10: RC 与发布闭环 (BLOCKED → PASS or BLOCKED_ACKNOWLEDGED)

**Scope:** 本地发布验证 (可做的部分) + 外部阻断确认

**Blockers (external):**
- macOS code signing certificate
- macOS notarization
- iOS Provisioning Profile

**What CAN be done:**
1. 本地 DMG 生成验证 (unsigned accepted)
2. Python wheel 安装验证
3. SBOM 完整性检查
4. Release Notes 完善
5. Operational Runbook 完善
6. 外部阻断正式文档化
7. Gate Acceptance Report (BLOCKED_ACKNOWLEDGED)

---

## 9.4 Execution Constraints (MUST FOLLOW)

```
✅ 每 Gate 完成后: 运行 tests + 生成 evidence + 更新 GATE_STATUS.json + local commit
✅ TDD: 先写 failing test → 实现 → green → refactor
✅ Single Writer: 每次只改一个 Gate 的文件
✅ Runtime Truth: UI 数据必须来自 API 权威状态，禁止 mock 伪装 live

❌ 禁止 push / merge / tag / deploy (除非用户明确批准)
❌ 禁止删除测试或降低断言来获得 PASS
❌ 禁止把 mock 结果说成 live 结果
❌ 禁止重建已有的权威能力 (G0-G6 已验证模块)
❌ 禁止在未批准的情况下执行 R3/R4 外部副作用
❌ 禁止修改 NSEC V2.1 或 Program Constitution
```

---

## 9.5 Human Intervention Triggers

只在以下情况暂停并请求人类介入：

1. **R3/R4 外部副作用** — 需要逐项审批
2. **不可逆产品决策** — 品牌名、定价、商业策略
3. **外部凭据阻断** — 代码签名证书、Provisioning Profile
4. **架构死锁** — 两个方案在现有证据下无法判定
5. **生产发布动作** — push/merge/tag/deploy
6. **不可恢复的数据迁移或破坏性变更**

---

## 9.6 State File Updates

每次 Gate 完成后更新以下文件：

```json
// .nexara/GATE_STATUS.json — 更新对应 Gate status
// .nexara/PROGRAM_STATE.json — 更新 current_gate, test_baseline, orchestration_status
// .nexara/EVIDENCE_MANIFEST.json — 追加新 evidence 引用
```

Commit message format:
```
feat(gate): G<N> <gate_name> — <brief result>

Tests: <N> passed, 0 failed
Evidence: reports/program/G<N>/
Gate: <PASS|PARTIAL|BLOCKED>

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 9.7 Final Acceptance: READY_FOR_HUMAN_APPROVAL

当以下条件全部满足时，程序终止于 READY_FOR_HUMAN_APPROVAL：

1. G7 状态 = PASS (或 BLOCKED_ACKNOWLEDGED with documented reason)
2. G8 状态 = PASS (至少一个 SDK 可安装可用)
3. G9 状态 = PASS (benchmark 执行 + evolution E2E)
4. G10 状态 = PASS (本地发布) 或 BLOCKED_ACKNOWLEDGED (外部阻断已文档化)
5. 所有测试通过 (682+ 新增)
6. 所有 evidence 已生成
7. GATE_STATUS.json 反映真实状态
8. Worktree clean, local commits 完整

**程序不自行决定 push/merge/deploy — 这些留给人类审批。**

---

## 9.8 Inventory Baseline Reference

本 G0 Reality Inventory 产出的所有文件：

| # | File | Purpose |
|---|------|---------|
| 01 | REALITY_INVENTORY_V2_20260723.md | 完整仓库盘点 |
| 02 | 02_target_to_existing_map.md | 目标→现有映射 |
| 03 | 03_authority_duplication_report.md | 权威/重复报告 |
| 04 | 04_gap_analysis.md | 缺口分析 (17 gaps) |
| 05 | 05_dependency_graph.md | 依赖图 |
| 06 | 06_development_gates.md | Gate 状态真值表 |
| 07 | 07_acceptance_matrix.md | 验收矩阵 |
| 08 | 08_program_state.md | 程序状态快照 |
| 09 | 09_claude_program.md | 本文件 — Claude 连续执行程序 |

**所有文件位于:** `reports/program/G0/`
**基线 HEAD:** dd0505ac53721d8e2e6150e47936119fe16734d6
**盘点完成时间:** 2026-07-23
