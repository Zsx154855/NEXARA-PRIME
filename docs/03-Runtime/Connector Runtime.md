---
id: CONNECTOR-RUNTIME
title: Connector Runtime
type: document
status: active
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
tags: [connector, runtime, security]
---
# Connector Runtime

NEXARA PRIME 的统一 Connector 抽象层。所有外部集成通过 Connector 接口接入。

## 内置 Connector

| Connector | 能力 | 风险等级 |
|-----------|------|----------|
| browser_readonly | navigate, read_dom, screenshot | R1 |
| http_readonly | GET, HEAD | R1 |
| provider | chat_completion, structured_output | R1 |

## 生命周期

UNREGISTERED → REGISTERED → CONFIGURED → STARTING → HEALTHY → STOPPING → STOPPED

## 安全边界

- 默认拒绝网络出站
- SSRF 防护（私网/Metadata/重定向验证）
- BrowserReadOnly 禁止 POST/上传/支付
- 所有调用生成 ConnectorReceipt + Evidence
