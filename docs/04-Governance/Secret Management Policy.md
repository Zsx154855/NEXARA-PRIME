---
id: SECRET-MGMT
title: Secret Management Policy
type: policy
status: active
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
tags: [security, secret, keychain]
---
# Secret Management Policy

## 默认后端

macOS Keychain（`/usr/bin/security`），账户 `nexara`。

## 规则

1. Secret 值不写入日志、Evidence、异常、Git
2. 只存储 Secret Reference（`keychain:nexara/path`）
3. Keychain 不可用时安全失败，不静默降级为明文文件
4. Environment 后端仅测试使用，需显式启用
5. `list` 只输出名称，不输出值
6. `set` 使用安全输入（getpass），不在命令历史暴露
