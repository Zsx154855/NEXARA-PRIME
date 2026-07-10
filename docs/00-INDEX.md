---
id: 00-INDEX
title: NEXARA Knowledge Fabric
type: map-of-content
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [map-of-content, knowledge-fabric]
---
# NEXARA Knowledge Fabric

这是 NEXARA PRIME 的人类认知层：用于理解产品、记录决策、追踪架构、审阅证据和维护项目记忆。

## 使用边界

- Obsidian：人类理解、链接、设计、决策和审阅。
- Git：文档版本、变更审查和回滚。
- NEXARA Runtime：Mission、Task、Approval、Tool、Memory 的运行事实。
- Evidence Ledger：不可变执行证据和审计链。
- Search Index：由 Canonical Source 和已批准 Memory 派生，不反向成为事实源。

## 快速入口

- [[01-Product/Product North Star]]
- [[02-Architecture/Knowledge Fabric Architecture]]
- [[02-Architecture/Three-Layer Model]]
- [[03-Runtime/Runtime Truth]]
- [[04-Governance/Source of Truth Policy]]
- [[04-Governance/Evidence Ledger Policy]]
- [[05-UI-UX/UI Truth Contract]]
- [[06-ADRs/README]]
- [[10-Data-Contracts/README]]
- [[11-Evaluations/README]]
- [[12-Operations/README]]
- [[_inbox/README]]
- [[_generated/README]]
- [[_templates/README]]
- [[maps/Canonical Source Map]]
- [[maps/NEXARA Prime Migration Map]]

## 三层产品模型

1. 人类决策核心：目标、价值、审批、暂停、接管、撤权、回滚。
2. Hermes + 8 位人格分身：编排、专业执行和人类可理解的角色表达。
3. L01–L12：将意图转化为可执行、可验证、可追溯结果的能力层。

## 工作规则

任何新功能先更新对象模型、状态机、数据契约和验收标准，再更新 UI。任何 UI 字段必须能追溯到 Runtime 对象或 Evidence。
