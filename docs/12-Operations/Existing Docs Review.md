---
id: EXISTING-DOCS-REVIEW
title: Existing NEXARA PRIME Docs Review
type: migration-review
status: review
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [migration, legacy, review]
---

# Existing NEXARA PRIME Docs Review

## Legacy Notes Purge — 2026-07-11

以下 10 份旧笔记已于 2026-07-11 清理，用户确认为个人笔记，不属于 NEXARA PRIME Canonical Source，已移至 `.trash/legacy-notes-20260711-051243/`。

| Legacy document | Status | Purge note |
|---|---|---|
| `ARCHITECTURE.md` | purged | 已由 02-Architecture/ 下的标准化文档替代 |
| `EVALUATION.md` | purged | 已由 11-Evaluations/ 替代 |
| `GOVERNANCE.md` | purged | 已由 04-Governance/ 替代 |
| `MEMORY.md` | purged | 已由 12-Operations/Knowledge Fabric Acceptance Report 中的 Memory 验收覆盖 |
| `MODEL_GATEWAY.md` | purged | 已由 02-Architecture/Three-Layer Model 覆盖 |
| `OBJECT_MODEL.md` | purged | 已由 10-Data-Contracts/ 对齐 |
| `PRODUCTION_HARDENING.md` | purged | 内容已纳入新架构层安全设计 |
| `STATE_MACHINE.md` | purged | 已由 03-Runtime/Runtime Truth 覆盖 |
| `TOOL_RUNTIME.md` | purged | 已由 02-Architecture/12-Layers/L06 Tools 覆盖 |
| `UI_SPEC.md` | purged | 已由 05-UI-UX/UI Truth Contract 替代 |

## 规则

新 Knowledge Fabric 文档负责权威导航和治理决策。旧笔记不再作为实现参考。任何冲突必须通过 ADR 解决。
