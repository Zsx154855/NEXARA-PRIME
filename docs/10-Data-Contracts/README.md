---
id: DATA-CONTRACTS-INDEX
title: Data Contracts
type: data-contract-index
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [data-contract-index, knowledge-fabric]
---
# Data Contracts

这里登记 Runtime 对象、JSON Schema、API 响应和 Obsidian 文档元数据契约。Schema 是可执行契约，Markdown 只负责解释和导航。

文档元数据规范：[[Document Frontmatter Schema]]。

## 最小对象集合

HumanIntent、ContextSnapshot、WorkContract、Mission、Task、AgentAssignment、ToolInvocation、ApprovalRequest、ExecutionReceipt、EvidenceArtifact、EvaluationResult、MemoryPatch、RollbackPoint。

## 规则

- 每个对象必须有稳定 ID、版本、状态、时间戳和 Trace ID。
- 文档不得伪造 Runtime 对象的当前状态。
- Schema 变更必须有 ADR 和兼容性说明。
