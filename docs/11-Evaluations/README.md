---
id: EVALUATIONS-INDEX
title: Evaluations
type: evaluation-index
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [evaluation-index, knowledge-fabric]
---
# Evaluations

这里保存 Benchmark、回归测试、Provider/Tool 评测和人工审阅结论。

## 评测门槛

- 正确性：任务目标达成率。
- 可靠性：成功、重试、恢复和幂等率。
- 安全性：未授权动作必须为 0。
- 可解释性：关键动作 Evidence 覆盖率。
- 效率：延迟、Token、成本和资源使用。
- 进化性：策略改进必须经过 Shadow Run 和 Promotion。
