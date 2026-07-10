---
id: ADR-007
title: ADR-007 — Network Deny-by-Default
type: adr
status: accepted
owner: human
created_at: 2026-07-11
tags: [adr, network, security]
---
# ADR-007: Network Deny-by-Default

## 决策

所有网络出站默认拒绝，通过显式 allowlist 授权。

## 理由

- SSRF 防护
- 最小权限原则
- DNS 解析后重新验证 IP
- 重定向后重新验证目标
