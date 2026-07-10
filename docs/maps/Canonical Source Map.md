---
id: CANONICAL-SOURCE-MAP
title: Canonical Source Map
type: source-map
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [source-map, knowledge-fabric]
---
# Canonical Source Map

| Source | Status | Canonical use |
|---|---|---|
| 原始 ZIP | immutable | 全部取证与追溯 |
| 优化版 Hermes 全闭环规范 | canonical candidate | orchestration / role contracts |
| 旧 Hermes 规范 | legacy | 历史参考，不直接编译 |
| 九层架构资料 | legacy / salvaged | 概念吸收至 L02/L04/L05/L12 |
| UI 视觉资产 | canonical visual reference | 明亮科幻、三层结构、动效语言 |
| 前端概念原型 | reference only | 交互和视觉灵感，不作为产品事实 |
| STEP 1 内核样例 | reference only | Event Bus、Registry、Logger 设计参考 |

## 裁决规则

内容完整度、架构一致性、工程可实施性优先；文件名和修改时间只能辅助判断。重复文件按 SHA256 去重。
