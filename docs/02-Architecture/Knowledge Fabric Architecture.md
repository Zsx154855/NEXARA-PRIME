---
id: KNOWLEDGE-FABRIC-ARCHITECTURE
title: Knowledge Fabric Architecture
type: architecture
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [architecture, knowledge-fabric]
---
# Knowledge Fabric Architecture

## 核心原则

```text
Immutable Sources
→ Canonical Documents
→ Human Knowledge Graph
→ Runtime Truth
→ Evidence Ledger
→ Derived Search / UI
```

## 事实源优先级

1. 原始资料：不可变，只读，用于追溯。
2. Canonical Source：经裁决的产品、架构、策略和数据契约。
3. Runtime Truth：当前任务和系统状态的唯一事实源。
4. Evidence Ledger：执行发生过什么的不可变事实源。
5. Obsidian Links：帮助人类理解，不覆盖运行事实。
6. 搜索索引：可重建的派生物，损坏后可重新生成。

## 数据流

```text
ZIP / 文档 / 视觉资产
        ↓ Source Forensics
Canonical Source + Legacy Map
        ↓ 人类审阅与 ADR
产品规范 / 架构 / 契约 / UI 规则
        ↓ 编译
Runtime Objects + Policies + Schemas
        ↓ 执行
Events + Receipts + Evidence + Memory Candidates
        ↓ 审阅
Obsidian 报告、索引和决策链接
```

## 禁止的反向流

- Obsidian 笔记不能直接改变 Mission 状态。
- 搜索索引不能直接写入 Canonical Memory。
- UI 展示值不能成为 Runtime 指标来源。
- 未经审批的候选 Memory 不能进入权威记忆。
