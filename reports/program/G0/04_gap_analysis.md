# 04 — Gap Analysis

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

基于 Blueprint §21 (Gate DAG) 和 §7 (Agent Domain Services) 对现有实现的全面缺口分析。

---

## 4.1 Critical Gaps (阻塞级)

### GAP-C01: AOS 源文件缺失 — 13 模块仅 .pyc

- **域:** Agent Orchestration System (aos/)
- **严重度:** CRITICAL
- **描述:** 13 个核心 AOS 模块 (supervisor, command_classifier, worker_adapters, execution_gateway, permission_broker, runtime_truth_adapter, cost_optimizer, recovery_engine, health_monitor, notification_gateway, policy_engine, loop_tool_adapter, context_compactor) 仅以编译后 .pyc 存在，无 .py 源文件
- **Blueprint 引用:** §12 Adaptive Multi-Role Scheduling, §7 Orchestration Service
- **影响:** 无法审计、修改或重建 AOS 子系统；违反 NSEC V2.1 第34条
- **修复方向:** 从其他 worktree/branch 恢复源文件，或基于 runtime.py 中已验证的 orchestration.py + program_loop.py 重建

### GAP-C02: GATE_STATUS.json 状态虚假

- **域:** Program State
- **严重度:** CRITICAL
- **描述:** GATE_STATUS.json 声称 G7/G8/G9 全部 PASS，但 Forensic Audit 证实 G7=PARTIAL, G8=NOT_STARTED, G9=PARTIAL
- **Blueprint 引用:** §23 Gate Execution Protocol — "执行器不得通过降低断言、删除测试、修改报告文本或把 mock 说成 live 获得 PASS"
- **影响:** 程序状态不可信；可能基于错误状态做出错误决策
- **修复方向:** 用 Forensic Audit 的 corrected_gate_status.json 覆盖 GATE_STATUS.json

### GAP-C03: SDK 目录为空壳

- **域:** Platform SDK (G8)
- **严重度:** HIGH
- **描述:** platform/sdk/swift/ 为空目录；platform/sdk/typescript/ 仅骨架；Python SDK 仅有基础 client.py + models.py；无插件 schema、签名验证或沙箱隔离
- **Blueprint 引用:** §19 API/SDK/Plugin Boundary
- **影响:** G8 声称 PASS 但实际 NOT_STARTED
- **修复方向:** 至少完成一个 SDK (推荐 Python) 的可安装发布

---

## 4.2 High Gaps (重大缺口)

### GAP-H01: L12 Evolution 闭环不完整

- **域:** Evolution (G9)
- **严重度:** HIGH
- **描述:** `evaluation.py` 有 EvaluationEngine, `product_reality/evolution.py` 有基础 pipeline, `benchmark_runner.py` 存在但独立执行证据不足。Blueprint 要求的 Observe→Diagnose→Candidate→Simulation→Benchmark→Approval→Deploy→Monitor→Rollback 全闭环未实现
- **Blueprint 引用:** §16 Evaluation & Evolution
- **影响:** 系统无法自我改进；G9 PARTIAL 状态正确

### GAP-H02: macOS/iOS 原生应用为初版骨架

- **域:** Product Experience (G7)
- **严重度:** HIGH
- **描述:** `experience/macos/` 和 `experience/ios/` 有基本 SwiftUI 视图但缺少: 真实 Runtime Truth API 绑定验证、screenshot 验收、可用性测试、iPad 独立布局
- **Blueprint 引用:** §18 产品体验蓝图 — "三端必须独立设计"
- **影响:** G7 PARTIAL 状态正确

### GAP-H03: Memory Graph UI 缺失

- **域:** Product Experience
- **严重度:** HIGH
- **描述:** Blueprint §18 规定 Memory Graph 为核心表面之一；`memory.py` 后端完整但前端无对应 UI 组件
- **Blueprint 引用:** §18 Memory Graph surface
- **影响:** 用户无法可视化记忆/知识图谱

### GAP-H04: Performance & Evolution UI 缺失

- **域:** Product Experience
- **严重度:** HIGH
- **描述:** Blueprint §18 规定的 Performance & Evolution 面板无前端实现
- **Blueprint 引用:** §18 Performance & Evolution surface

---

## 4.3 Medium Gaps (中等缺口)

### GAP-M01: agent/ 和 platform/ 子包仅骨架

- **域:** Agent Domain
- **描述:** `src/nexara_prime/agent/__init__.py` 和 `src/nexara_prime/platform/__init__.py` 都是空骨架
- **Blueprint 引用:** §7.1 推荐代码边界 — agent/ 应有 16 个模块
- **影响:** 代码组织未达到 blueprint 推荐结构

### GAP-M02: ImprovementProposal 对象模型缺失

- **域:** Object Model
- **描述:** Blueprint §9 定义的 ImprovementProposal 对象 (proposal_id, target, evidence, hypothesis, experiment_plan, rollback) 未在 models.py 中实现
- **影响:** Evolution 闭环缺少核心数据模型

### GAP-M03: Telemetry Service 隐式实现

- **域:** Platform Services
- **描述:** EventBus 记录了事件流但没有专门的 Telemetry 聚合/导出服务
- **Blueprint 引用:** §17 Observability — Telemetry 记录 Mission/Task/Provider/Token/Cost/Approval/Failure/Recovery
- **影响:** 缺乏结构化可观测性数据

### GAP-M04: Planning Simulation 缺失

- **域:** Planning
- **描述:** Blueprint §7 要求 "Planning & Simulation Service" 含多路径模拟、资源分配、风险/成本预测
- **现有:** 仅 `adaptive_scheduler.py` 做 ROI-gated 分配，无模拟能力
- **影响:** 无法在执行前预测资源消耗和风险

### GAP-M05: Plugin 架构完全缺失

- **域:** Extensions
- **描述:** Blueprint §19 要求插件进程隔离/沙箱、权限声明、签名验证；`extensions/` 仅含 README
- **影响:** 无法加载第三方能力扩展

---

## 4.4 Low Gaps (次要缺口)

### GAP-L01: UI 无自定义 hooks

- **域:** UI
- **描述:** `ui/src/hooks/` 为空目录；所有状态管理直接使用 useState/useEffect
- **影响:** 可维护性降低，无复用逻辑提取

### GAP-L02: UI 无测试

- **域:** UI
- **描述:** 零前端测试文件；无 Playwright/Vitest/Jest/React Testing Library 依赖
- **Blueprint 引用:** §25 测试金字塔 — UI Runtime Truth 层
- **影响:** 无前端回归保护

### GAP-L03: 无 CI Runner 可用

- **域:** CI/CD
- **描述:** PROGRAM_STATE.json 记录 CI_PLATFORM_FAILURE — "No GitHub Actions runner allocated"
- **影响:** CI 流水线无法实际运行

### GAP-L04: 产品品牌名未定

- **域:** Product
- **描述:** Blueprint 多次提及 "产品名待定"；PROGRAM_STATE.json 记录 PRODUCT_DECISION_PENDING
- **Blueprint 引用:** §0 内部代号 NEXARA Sovereign Agent
- **影响:** 发布阻塞 (G10 blocker)

### GAP-L05: 代码签名证书缺失

- **域:** Release
- **描述:** PROGRAM_STATE.json external_blockers: macOS code signing certificate, notarization, iOS Provisioning Profile
- **影响:** G10 DMG/IPA 分发阻塞

---

## 4.5 Gap Summary

| Severity | Count | Area |
|----------|-------|------|
| CRITICAL | 3 | AOS sources, Gate state truth, SDK emptiness |
| HIGH | 4 | Evolution loop, Native apps, Memory UI, Perf UI |
| MEDIUM | 5 | Agent skeleton, ImprovementProposal, Telemetry, Simulation, Plugins |
| LOW | 5 | UI hooks, UI tests, CI runner, Brand name, Code signing |
| **TOTAL** | **17** | |

---

## 4.6 Blueprint Coverage by Domain

| Domain | Blueprint Weight | Actual Maturity | Gap |
|--------|-----------------|-----------------|-----|
| Runtime Kernel | 20 | 4.3/5 → 4.5/5 (improved) | Minor |
| 治理与安全 | 15 | 4.2/5 → 4.4/5 (improved) | Minor |
| Evidence/Memory/Recovery | 15 | 3.8/5 → 4.0/5 (improved) | Minor |
| Platform Services | 15 | 1.8/5 → 2.5/5 | **Significant** |
| 第一方 Agent Domain | 15 | 0.5/5 → 3.0/5 | **Major improvement but gaps remain** |
| 产品体验 | 7 | 1.0/5 → 2.0/5 | **Significant** |
| SDK/Plugin/Ecosystem | 3 | 0.5/5 → 0.8/5 | **Major** |
| Provider/SecretStore | 10 | 4.1/5 → 4.3/5 (improved) | Minor |

**当前加权成熟度: ~3.3/5 (66%)** — 比 Blueprint 编写时的 2.9/5 (58%) 提升了 8 个百分点，主要来自 Agent Identity + Mission 闭环的实现。
