---
id: ADR-006
title: ADR-006 — macOS Keychain as Default Secret Backend
type: adr
status: accepted
owner: human
created_at: 2026-07-11
tags: [adr, secret, keychain, security]
---
# ADR-006: macOS Keychain as Default Secret Backend

## 决策

默认使用 macOS Keychain 存储 Secret，不自行管理加密文件。

## 理由

- 系统级安全隔离
- 无需额外密钥管理
- 应用间不共享
- 不可用时安全失败
