---
id: ADR-001
title: ADR-001 Use Knowledge Fabric
type: adr
status: approved
owner: human
source_of_truth: git
runtime_effect: policy
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [adr, knowledge-fabric]
---
# ADR-001：采用 Knowledge Fabric

## Decision

采用 Obsidian + Git + Runtime Truth + Evidence Ledger 的分层方案。

## Rationale

Obsidian 擅长人类理解和知识链接，但不适合作为 Mission 状态、审批或安全事实源。分层可以同时获得可读性、版本性、可恢复性和审计性。

## Consequences

- 需要维护 Source of Truth 边界。
- Obsidian 内容必须进入 Git 审阅。
- Runtime 与 Evidence 需要独立存储和校验。
