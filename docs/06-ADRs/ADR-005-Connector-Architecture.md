---
id: ADR-005
title: ADR-005 — Connector Architecture
type: adr
status: accepted
owner: human
created_at: 2026-07-11
tags: [adr, connector, architecture]
---
# ADR-005: Connector Architecture

## 决策

采用统一 Connector 抽象层管理所有外部集成。

## 理由

- 统一生命周期管理
- 统一权限和审计
- 故障隔离（熔断器）
- Evidence 自动绑定
- Secret 引用而非存储
