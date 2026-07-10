---
id: RUNTIME-TRUTH
title: Runtime Truth
type: runtime-policy
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [runtime-policy, knowledge-fabric]
---
# Runtime Truth

## 权威对象

HumanIntent、ContextSnapshot、WorkContract、Mission、Task、AgentAssignment、ToolInvocation、ApprovalRequest、ExecutionReceipt、EvidenceArtifact、EvaluationResult、MemoryPatch、RollbackPoint。

## 规则

- Mission 状态只能由 State Machine 改变。
- UI 只读投影 Runtime，不直接创造状态。
- 每个可执行动作都有风险等级、权限、预算、超时和幂等键。
- 多读者、多分析者、多审查者，单写者。
- Runtime 事件和 Evidence 必须可重放、可校验、可审计。

## 自适应执行档位

| Profile | 使用场景 | 典型链路 |
|---|---|---|
| S0 Instant | 问答、翻译、摘要 | Intent → Result |
| S1 Assisted | 单工具、低风险文件任务 | Intent → Plan → Tool → Receipt |
| S2 Managed | 多步骤、中风险任务 | Contract → Agents → Verify → Evidence |
| S3 Governed | 外部后果、高风险变更 | Simulation → Approval → Execute → Rollback |
