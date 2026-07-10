---
id: SOURCE-OF-TRUTH-POLICY
title: Source of Truth Policy
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
# Source of Truth Policy

## 不可变原则

原始 ZIP、原始图片、原始 PDF 和取证 Hash 不删除、不覆盖。旧版进入 Legacy，不从历史中抹除。

## Canonical 原则

同一概念只能有一个 Canonical 定义。冲突通过 ADR 解决，不能在多个笔记中各自维护“最终版”。

## 修改流程

```text
Draft
→ Review
→ ADR / Approval
→ Canonical
→ Runtime / UI 编译
```

## Obsidian 规则

- Vault 中的 Markdown 纳入 Git。
- 运行时生成内容使用 `generated` 标记，不手工伪装成 Canonical。
- Dataview、图谱和索引都是可重建派生物。
- 不把 API Key、Token、个人隐私和未经审查的运行数据库复制到 Vault。
