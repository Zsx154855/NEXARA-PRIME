# ORPHAN TOOL RECEIPT — AUDIT NOTE (P4)

## 对象
tool_6000d9317d3b — code_exec, status=completed, receipt_evidence_id=None

## 分类
historical-data anomaly（历史数据异常），非当前 Runtime 缺陷。

## 证据
- 时间：2026-08-15T11:23:29（2 天前，历史记录）
- mission_4379b06ba743 state=Completed
- 同 mission 同时间点兄弟 tool 均有 receipt：
  - tool_5d5f6d31ac9e（code_exec）→ receipt=evidence_7a6bde716c98
  - tool_b7405a234867（file_write_report）→ receipt=evidence_d21bdcac44ea
- 全库 tool 统计：51 个 tool，仅此 1 个孤儿（其余 50 个均含 receipt）
- 8-13 / 8-15 / 8-16 / 8-17 所有其他 tool 均正常 → 无系统性缺陷
- 该 tool 是 code-check 探针（idempotency_key=mission_4379b06ba743:code-check），
  为运行时健康检查的 code_exec 探针，receipt 生成走特殊路径

## 结论
1. 历史遗留（2026-08-15 特定时间点），非当前 Runtime 缺陷（现无新孤儿）
2. 非数据迁移问题（运行时自身产生）
3. 禁止修改历史 Evidence —— 保留原记录不动

## 处理
- 保留 tool_6000d9317d3b 原始记录（未修改）
- 创建本 audit note，分类 historical-data anomaly
- 无需数据修复（单一历史异常，不影响运行时正确性）
