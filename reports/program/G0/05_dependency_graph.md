# 05 — Dependency Graph

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

---

## 5.1 模块依赖图 (Python Runtime)

```
┌─────────────────────────────────────────────────────────────┐
│                        NexaraRuntime                        │
│                       (runtime.py)                          │
│              中央编排器 — 依赖注入所有子系统                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌─────────┐    ┌──────────────┐    ┌──────────────┐
│  config │    │   identity   │    │ state_machine│
│ (环境变量) │    │ (Agent/User/ │    │ (Mission状态  │
│         │    │  Device/Sess) │    │  转换规则)    │
└─────────┘    └──────────────┘    └──────────────┘
                       │
    ┌──────────────────┼──────────────────────────────────┐
    │                  │                                  │
    ▼                  ▼                                  ▼
┌─────────┐    ┌──────────────┐                   ┌──────────────┐
│   db    │◄───│    events    │                   │   models     │
│SQLiteStore│  │   EventBus   │                   │(所有dataclass)│
│(持久化层) │   │  (事件流)     │                   │              │
└────┬────┘    └──────┬───────┘                   └──────────────┘
     │                │
     ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    核心服务层 (依序依赖)                        │
│                                                             │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐  │
│  │ evidence │  │ governance│  │  memory   │  │evaluation│  │
│  │(SHA-256  │  │(R0-R4策略)│  │(四层记忆) │  │(评分引擎) │  │
│  │ hash链)  │  │(审批引擎) │  │(冲突消解) │  │          │  │
│  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬─────┘  │
│       │              │              │              │         │
│  ┌────┴──────────────┴──────────────┴──────────────┴────┐   │
│  │                   能力/执行层                          │   │
│  │  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │capabilities│  │  tools   │  │mission_compiler  │  │   │
│  │  │(能力注册表)│  │(工具运行时)│  │(目标→MissionSpec) │  │   │
│  │  └────────────┘  └──────────┘  └──────────────────┘  │   │
│  │  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │contract_eng│  │ scheduler│  │ model_gateway    │  │   │
│  │  │(合约引擎)  │  │(角色调度)│  │(Provider抽象)    │  │   │
│  │  └────────────┘  └──────────┘  └──────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│sandbox_v2│    │  recovery    │    │real_context  │
│(沙箱执行) │    │(崩溃恢复)     │    │(Git上下文)   │
└──────────┘    └──────────────┘    └──────────────┘
```

---

## 5.2 编排层依赖 (双重执行循环)

```
┌─────────────────────┐     ┌───────────────────────────┐
│   program_loop.py   │     │    orchestration.py        │
│  (后台循环守护进程)    │     │   (持久控制平面)             │
│                     │     │                           │
│  Load → Select →    │     │  MissionQueue             │
│  Acquire → Execute  │     │  WorkerScheduler          │
│  → Verify → Persist │     │  WriterLeaseManager       │
│  → Checkpoint →     │     │  ApprovalQueue            │
│  Schedule           │     │  RecoveryQueue            │
│                     │     │  EvidenceQueue            │
└──────────┬──────────┘     └─────────────┬─────────────┘
           │                              │
           └──────────┬───────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │  NexaraRuntime  │
            │  (runtime.py)   │
            │  5-stage engine │
            └─────────────────┘
```

**依赖关系:** program_loop.py 和 orchestration.py 都直接依赖 NexaraRuntime。这两个模块是平行控制平面，存在功能重叠但无循环依赖。

---

## 5.3 AOS 子系统依赖 (仅 .pyc — 推断)

```
┌─────────────────────────────────────────────┐
│              supervisor (58.6K)              │
│              主监督器/协调器                   │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌──────────┐ ┌───────────┐ ┌──────────────┐
│ command  │ │ worker    │ │ execution    │
│classifier│ │ adapters  │ │ gateway      │
│(46.4K)   │ │(23.4K)    │ │(12.4K)       │
└────┬─────┘ └─────┬─────┘ └──────┬───────┘
     │             │              │
     ▼             ▼              ▼
┌──────────┐ ┌───────────┐ ┌──────────────┐
│ context  │ │permission │ │ runtime_truth│
│compactor │ │ broker    │ │ adapter      │
│(3.7K)    │ │(9.3K)     │ │(8.4K)        │
└──────────┘ └─────┬─────┘ └──────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌──────────┐ ┌───────────┐ ┌──────────────┐
│ policy   │ │ recovery  │ │ health       │
│ engine   │ │ engine    │ │ monitor      │
│(5.2K)    │ │(6.4K)     │ │(5.6K)        │
└──────────┘ └───────────┘ └──────────────┘
┌──────────────┐ ┌──────────────┐ ┌──────────┐
│ notification │ │ cost         │ │ loop_tool│
│ gateway      │ │ optimizer    │ │ adapter  │
│(5.3K)        │ │(8.5K)        │ │(4.3K)    │
└──────────────┘ └──────────────┘ └──────────┘
```

**注意:** 此依赖图从 .pyc import 分析推断，可能不完整。

---

## 5.4 UI 组件依赖图

```
page.tsx
  └── DashboardShell.tsx (SPA router + data fetching)
        ├── Sidebar.tsx
        ├── TopBar.tsx
        └── screens/
              ├── Overview.tsx
              │     └── StatCard, Skeleton, StateRail
              ├── MissionCreator.tsx
              │     └── StepIndicator, ConfirmDialog
              ├── MissionWorkspace.tsx
              │     └── StateRail, EventTimeline, ToolList, ConfirmDialog
              ├── AgentTeam.tsx
              ├── ApprovalCenter.tsx
              │     └── ApprovalCard, HistoryCard, ConfirmDialog
              ├── CapabilityRegistry.tsx
              │     └── CapabilityCard
              ├── EvidenceViewer.tsx
              │     └── EvidenceRow
              └── RuntimeHealth.tsx
                    └── HealthBadge, Section, StatRow, Skeleton

依赖:
  lib/api.ts ← 所有 screens (通过 DashboardShell props 传递)
  lib/utils.ts ← 所有 components
  types/index.ts ← 所有 components + lib/api.ts
  lucide-react ← Sidebar, TopBar, screens (图标)
```

---

## 5.5 外部依赖图

```
NEXARA-PRIME
  ├── Python 3.12.13
  │     ├── fastapi >= 0.110
  │     ├── pydantic >= 2.6
  │     └── uvicorn >= 0.29
  ├── Next.js 16 + React 19
  │     ├── tailwindcss v4
  │     ├── lucide-react
  │     └── clsx + tailwind-merge
  ├── Swift 5.9
  │     └── SwiftUI (macOS .v14, iOS .v17)
  ├── DeepSeek API (live provider)
  │     └── macOS Keychain (credentials)
  └── SQLite (WAL mode, via Python stdlib)
```

---

## 5.6 Gate 依赖 DAG (Blueprint §22)

```
G0 (产品宪章)
 │
 └─→ G1 (Agent Identity)
      │
      └─→ G2 (Mission 闭环)
           │
           ├─→ G3 (Platform Services) ──→ G4 (Capability Runtime)
           │                                      │
           │                                      └─→ G5 (Memory Fabric)
           │                                               │
           │                                               └─→ G6 (Governance)
           │                                                        │
           │                                                        └─→ G7 (三端体验)
           │                                                                 │
           │                                                                 └─→ G8 (SDK)
           │                                                                          │
           │                                                                          └─→ G9 (Evolution)
           │                                                                                   │
           │                                                                                   └─→ G10 (RC)
           │
           └─→ G5 可与 G3 并行 (在 G2 核心对象冻结后)
```

**当前状态 (Forensic Audit 修正后):** G0-G6 PASS. 最早未完成 Gate: **G7 (PARTIAL)**.

---

## 5.7 关键循环依赖检查

| 检查 | 结果 |
|------|------|
| Python 模块间循环依赖 | ✅ 无 — runtime.py 单向注入所有子系统 |
| 事件循环依赖 | ✅ 无 — EventBus 单向发布/订阅 |
| UI ↔ Runtime 循环 | ✅ 无 — UI 通过 HTTP API 单向读取 |
| 双重执行循环冲突 | ⚠️ program_loop + orchestration 平行运行 |
| AOS ↔ Runtime 循环 | ❓ 无法验证 (源码缺失) |
