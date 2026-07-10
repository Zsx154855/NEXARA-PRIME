---
id: ADR-004
title: ADR-004 No Blacklist Sandbox
type: adr
status: review
owner: human
source_of_truth: git
runtime_effect: policy
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [adr, knowledge-fabric]
---
# ADR-004：禁止以黑名单代替沙箱

工具执行必须使用 OS 级隔离、路径白名单、网络策略、资源限制和进程生命周期管理。字符串黑名单只能作为辅助防护，不能成为安全边界。
