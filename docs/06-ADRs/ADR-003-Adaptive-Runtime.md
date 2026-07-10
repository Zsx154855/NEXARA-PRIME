---
id: ADR-003
title: ADR-003 Adaptive Runtime
type: adr
status: draft
owner: human
source_of_truth: git
runtime_effect: policy
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [adr, knowledge-fabric]
---
# ADR-003：采用自适应运行档位

简单任务走 S0/S1，复杂和高风险任务逐级升级至 S2/S3。目标是把 Runtime 的复杂度从固定负担转化为按需能力。
