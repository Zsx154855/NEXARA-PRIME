# 02 — Target-to-Existing Map

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

Blueprint §7 规定的 Target Architecture vs 实际实现映射。

---

## 2.1 十二层架构 (L01-L12) 实现映射

| Layer | Blueprint Target | Existing Implementation | Status |
|-------|-----------------|------------------------|--------|
| L01 Intent | IntentRecord, GoalGraph, MissionCompiler | `mission_compiler.py` + `mission_triage.py` — 目标编译为结构化 MissionSpec，含风险/边界/约束 | **PASS** |
| L02 Context | ContextSnapshot, WorldState, Git/文件/知识/日历 | `real_context.py` — RealRepositoryContext + context_hash; `rag_pipeline.py` — RAG 知识检索 | **PASS** |
| L03 Contract | WorkContract, 固定输入/输出/边界/预算/审批 | `contract_engine.py` — WorkContract 生命周期管理 | **PASS** |
| L04 Planning | Plan, TaskGraph, 依赖/并行/检查点 | `adaptive_scheduler.py` — ROI-gated 动态角色分配; `scheduler.py` — 角色→Persona 映射 | **PASS** |
| L05 Reasoning | DecisionRecord, 模型路由/反事实/风险成本 | `model_router.py` — ProviderInfo 路由; `model_gateway.py` — 多 Provider 抽象 | **PASS** |
| L06 Capabilities | CapabilityManifest, Registry, Score | `capabilities.py` — CapabilityRegistry V1+V2 统一注册/评分 | **PASS** |
| L07 Execution | ExecutionRun, ToolCall, Single Writer, 沙箱 | `runtime.py` — NexaraRuntime 5-stage; `sandbox_v2.py` — macOS sandbox-exec; `orchestration.py` — WriterLease | **PASS** |
| L08 Verification | VerificationReport, 测试/断言/回归/验收 | `evaluation.py` — EvaluationEngine; `independent_review.py` — 独立审查 | **PASS** |
| L09 Evidence | EvidenceEnvelope, Receipt, SHA-256 hash chain | `evidence.py` — EvidenceStore + receipt chain verify | **PASS** |
| L10 Memory | MemoryItem, MemoryPatch, 五类记忆模型 | `memory.py` — MemoryKernel 四层架构 + MemoryLayerManager | **PASS** |
| L11 Governance | PolicyDecision, R0-R4, Approval, NSEC | `governance.py` — PolicyEngine + ApprovalEngine + WriterLeaseManager; NSEC V2.1 | **PASS** |
| L12 Evolution | ImprovementProposal, Experiment, Benchmark | `evaluation.py` + `product_reality/evolution.py` — EvaluationEngine + Evolution pipeline | **PARTIAL** |

**L12 问题:** Evolution 闭环不完整 — benchmark_runner 存在但独立执行证据不充分 (Forensic Audit 指认 G9 PARTIAL)。

---

## 2.2 第一方 Agent Domain 服务映射

| Blueprint Service | Existing Module | Coverage |
|-------------------|-----------------|----------|
| Agent Identity Service | `identity.py` — AgentIdentity + 10 原则 + 22 capabilities | ✅ Full |
| Mission Service | `mission_compiler.py` + `state_machine.py` + `cli.py` | ✅ Full |
| Context / World Model Service | `real_context.py` + `rag_pipeline.py` | ✅ Full |
| Contract Service | `contract_engine.py` | ✅ Full |
| Planning & Simulation Service | `adaptive_scheduler.py` + `scheduler.py` | ⚠️ No simulation |
| Orchestration Service | `orchestration.py` + `program_loop.py` + `adaptive_runtime.py` | ✅ Full |
| Capability Registry Service | `capabilities.py` | ✅ Full |
| Policy & Approval Service | `governance.py` + `identity.py` | ✅ Full |
| Execution Service | `runtime.py` + `sandbox_v2.py` + `tools.py` | ✅ Full |
| Verification Service | `evaluation.py` + `independent_review.py` | ✅ Full |
| Evidence & Audit Service | `evidence.py` + `security_audit.py` + `connectors/audit.py` | ✅ Full |
| Memory & Knowledge Service | `memory.py` + `rag_pipeline.py` | ✅ Full |
| Evaluation & Evolution Service | `evaluation.py` + `product_reality/evolution.py` | ⚠️ Benchmark gap |
| Telemetry Service | `events.py` (EventBus) + API routes | ⚠️ Implicit only |

---

## 2.3 产品体验蓝图映射

| Blueprint Surface | Existing | Status |
|-------------------|----------|--------|
| Mission Composer | `ui/.../screens/MissionCreator.tsx` — 3步向导 | ✅ Web |
| Mission Workspace | `ui/.../screens/MissionWorkspace.tsx` — 状态rail+步骤+事件 | ✅ Web |
| Live Runtime | `ui/.../screens/RuntimeHealth.tsx` + `ui/.../screens/Overview.tsx` | ✅ Web |
| Approval Center | `ui/.../screens/ApprovalCenter.tsx` — 待审批/历史 tabs | ✅ Web |
| Evidence Ledger | `ui/.../screens/EvidenceViewer.tsx` — 可搜索可展开 | ✅ Web |
| Memory Graph | ❌ 无专用 UI | ❌ Missing |
| Capability Control | `ui/.../screens/CapabilityRegistry.tsx` | ✅ Web |
| Performance & Evolution | ❌ 无专用 UI | ❌ Missing |
| **macOS 专业工作台** | `experience/macos/` — 5个详情视图 + ViewModel | ⚠️ 初版 |
| **iPad 任务指挥** | `experience/ios/` — AdaptiveContentView (TabView/NavigationSplitView) | ⚠️ 初版 |
| **iPhone 状态/审批** | `experience/ios/` — iPhoneTabs 4 tabs | ⚠️ 初版 |

---

## 2.4 SDK/Plugin 边界映射

| Blueprint Target | Existing | Status |
|------------------|----------|--------|
| Python SDK | `platform/sdk/python/nexara_sdk/` — client.py + models.py | ⚠️ Basic |
| TypeScript SDK | `platform/sdk/typescript/src/index.ts` | ⚠️ Skeleton |
| Swift SDK | `platform/sdk/swift/` | ❌ Empty |
| REST API | `platform/sdk/rest/openapi.yaml` + `api.py` (FastAPI) | ✅ |
| MCP | `platform/sdk/mcp/server.py` | ⚠️ Basic |
| Plugin schema | ❌ | ❌ Missing |
| Plugin sandbox/隔离 | ❌ | ❌ Missing |
| Plugin 签名验证 | ❌ | ❌ Missing |

---

## 2.5 推荐仓库结构 (Blueprint §21) vs 实际

| Blueprint Target Path | Actual Path | Delta |
|----------------------|-------------|-------|
| `src/nexara_prime/agent/` | `src/nexara_prime/agent/` | ⚠️ 仅 `__init__.py` 骨架 |
| `src/nexara_prime/platform/` | `src/nexara_prime/platform/` | ⚠️ 仅 `__init__.py` 骨架 |
| `src/nexara_prime/kernel/` | 顶级模块散落在 `src/nexara_prime/` | ❌ 未按 blueprint 分层 |
| `experience/macos/` | `experience/macos/` | ✅ |
| `experience/ios/` | `experience/ios/` | ✅ |
| `experience/web/` | `ui/` | ✅ (路径不同) |
| `sdk/python/` | `platform/sdk/python/` | ✅ |
| `sdk/typescript/` | `platform/sdk/typescript/` | ✅ |
| `sdk/swift/` | `platform/sdk/swift/` | ✅ |
| `sdk/mcp/` | `platform/sdk/mcp/` | ✅ |
| `plugins/` | `extensions/` | ⚠️ 路径不同，内容空 |
| `contracts/` | `schemas/` | ✅ |
| `evals/` | 嵌入 `reports/` + `tests/` | ⚠️ 未独立 |
| `docs/PRODUCT_CONSTITUTION.md` | `NEXARA_PROGRAM_CONSTITUTION_V1.md` (root) | ✅ |
| `docs/ARCHITECTURE.md` | `NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md` (root) | ✅ |
| `.nexara/PROGRAM_STATE.json` | `.nexara/PROGRAM_STATE.json` | ✅ |
| `.nexara/GATE_STATUS.json` | `.nexara/GATE_STATUS.json` | ✅ |

---

## 2.6 核心对象模型映射

| Blueprint Object | Existing Model (models.py) | Status |
|------------------|---------------------------|--------|
| AgentIdentity | `AgentIdentity` dataclass | ✅ |
| Mission | `Mission` + `MissionSpec` dataclasses | ✅ |
| WorkContract | `WorkContract` dataclass | ✅ |
| Plan | `MissionPlan` + `PlanStep` dataclasses | ✅ |
| Task | `MissionQueueItem` (orchestration) | ✅ |
| Capability | `Capability` + `CapabilityScore` dataclasses | ✅ |
| PolicyDecision | `ApprovalRequest` + PolicyEngine | ✅ |
| ExecutionRun | `ToolInvocation` + runtime.py ExecutionContext | ✅ |
| EvidenceEnvelope | `EvidenceArtifact` dataclass | ✅ |
| MemoryItem | `MemoryRecord` dataclass | ✅ |
| ImprovementProposal | ❌ 无专用模型 | ❌ Missing |

---

## 2.7 AOS 子系统映射

| AOS Module (bytecode only) | 推断功能 | Blueprint §12 映射 |
|---------------------------|---------|-------------------|
| `supervisor.pyc` (58.6K) | 主监督器 | Orchestration Service |
| `command_classifier.pyc` (46.4K) | 命令分类 | S0-S3 triage |
| `worker_adapters.pyc` (23.4K) | Worker 适配器 | 动态角色 |
| `execution_gateway.pyc` (12.4K) | 执行网关 | Execution Service |
| `permission_broker.pyc` (9.3K) | 权限代理 | Policy Service |
| `runtime_truth_adapter.pyc` (8.4K) | Runtime Truth | UI ↔ Runtime |
| `cost_optimizer.pyc` (8.5K) | 成本优化 | Token经济学 |
| `recovery_engine.pyc` (6.4K) | 恢复引擎 | Recovery |
| `health_monitor.pyc` (5.6K) | 健康监控 | Telemetry |
| `notification_gateway.pyc` (5.3K) | 通知网关 | UI |
| `policy_engine.pyc` (5.2K) | 策略引擎 | Governance |
| `loop_tool_adapter.pyc` (4.3K) | 循环工具适配 | Execution |
| `context_compactor.pyc` (3.7K) | 上下文压缩 | Token Compiler |

**严重问题:** 13 个 AOS 模块仅有 `.pyc` 字节码，无源文件。`git` 中可能从未提交源文件，或已被清理。这意味着 AOS 子系统无法从源码重建，且违反了 NSEC 源码完整性要求。

---

## 2.8 覆盖率总表

| Domain | Target | Existing | % |
|--------|--------|----------|---|
| Runtime Kernel | L07+L08+L01-L06 integration | 62 .py files, 682 tests | 95% |
| Governance | NSEC V2.1 + R0-R4 + Approval | governance.py + NSEC docs | 90% |
| Evidence/Memory | E0-E2 + 五类记忆 | evidence.py + memory.py | 85% |
| Platform Services | Capability/Policy/Telemetry/Knowledge | Scattered but functional | 75% |
| First-Party Agent | Identity + Mission + Memory namespace | identity.py + mission_compiler | 80% |
| Product Experience | Web + macOS + iOS | 8 screens + 2 native apps | 60% |
| SDK/Plugin | Python/TS/Swift/REST/MCP | Scaffolds only | 15% |
| Evaluation/Evolution | Benchmark + Regression + Experiment | Partial implementation | 40% |
| AOS Daemon | 13 modules | .pyc only (source MISSING) | 0% (unrecoverable) |
| CI/CD | GitHub Actions | ci.yml exists, runner failures | 40% |
