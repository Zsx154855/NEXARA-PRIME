---
id: EVIDENCE-LEDGER-POLICY
title: Evidence Ledger Policy
type: governance-policy
status: canonical
owner: human
source_of_truth: git
runtime_effect: policy
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [governance-policy, knowledge-fabric]
---
# Evidence Ledger Policy

每个 Evidence 必须携带：

```text
Evidence ID
Mission ID
Task ID
Actor
Timestamp
Source Event
Tool Invocation
Content Hash
Metadata Hash
Parent Evidence
Verification Status
```

## 分层

- E0 Transient：短期调试信息，可过期。
- E1 Operational：任务执行和验证证据，按项目保留。
- E2 Critical：审批、外部后果、发布、删除、最终交付物，长期不可变保留。

## Completed 门槛

Contract 验收条件满足、关键 Evidence 齐全、审批与动作匹配、Evaluation 通过、无未处理阻塞、Rollback Point 有效。
