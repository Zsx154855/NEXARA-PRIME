---
id: NETWORK-POLICY
title: Network Egress Policy
type: policy
status: active
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
tags: [network, security, policy]
---
# Network Egress Policy

## 默认策略

deny-by-default。所有外部网络访问必须通过 NetworkPolicyEngine。

## 允许

- HTTPS 443 / HTTP 80
- Domain allowlist 中的目标
- GET / HEAD 方法

## 拒绝

- 私网 IP（RFC1918）
- Metadata endpoint（169.254.169.254）
- file/javascript/data/ftp scheme
- POST/PUT/PATCH/DELETE 外部请求
- 未声明的网络能力
