---
id: UI-TRUTH-CONTRACT
title: UI Truth Contract
type: ui-contract
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [ui-contract, knowledge-fabric]
---
# UI Truth Contract

## 三种视图

- Focus View：当前任务、待审批、异常、下一步、目标输入。
- Operator View：执行链、智能体、工具、Evidence、Runtime。
- Architect View：12 层、Capability Graph、Policy、Memory、调度和资源。

## 视觉原则

- 暖白、薰衣草、香槟金为主；紫色只承担 Hermes、选中和主操作。
- 绿色表示正常/完成，琥珀表示等待/审批，红色表示阻塞/危险，蓝色表示工具/外部连接。
- 科幻动效服务状态和因果链，不作为持续装饰。
- 移动端独立设计，不缩放桌面布局。

## 禁止显示

没有来源、公式、采样时间和阈值的伪指标不得进入产品页面。

## UI 验收

每个动作必须有 Default、Loading、Success、Error、Disabled、Permission Required 状态；每个字段必须能链接到 Runtime 对象或 Evidence。
