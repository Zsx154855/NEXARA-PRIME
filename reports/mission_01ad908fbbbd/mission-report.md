# NEXARA PRIME Mission Report

- Mission: `mission_01ad908fbbbd`
- Title: 执行任务：检查当前运行时健康状态并生成一份简短报告。
- Risk: R2
- Provider: deepseek

## Verified repository facts

- Repository Branch: `not_applicable`
- Repository HEAD: `not_applicable`
- Repository Dirty: `False`
- Repository Files: `0`
- Context Hash: `not_applicable`
- Environment Limitation: `none`

## Compiled task

执行任务：检查当前运行时健康状态并生成一份简短报告。

## Result

NEXARA PRIME / mission_id: `mission_01ad908fbbbd`

状态机轨迹：
```text
INIT -> INSPECT_CONTEXT -> CHECK_CAPABILITIES -> COLLECT_EVIDENCE -> EVALUATE_GATES -> DRAFT_REPORT -> AWAIT_APPROVAL
```

证据：
- 已检查 `source_dir: workspace`
- `NEXARA bounded repository context` 为空：
  - `files: []`
  - `excerpts: []`
  - `branch: null`
  - `head_sha: null`
  - `repository: null`
- 未发现可读取的运行时健康指标、日志或状态文件
- 未接触外部系统
- 未删除或覆盖任何源材料

安全门：`PASS`  
证据门：`FAIL` — 缺少运行时健康检查数据或已挂载的检查能力，无法完成可验证的健康评估。

简短健康报告（草稿，待批准后正式生效）：

> 当前运行时健康状态：未知/无法验证。  
> 原因：本地 workspace 无可读文件，仓库上下文为空，且未提供运行时健康检查工具或状态数据。  
> 建议：挂载只读健康检查能力或提供运行时状态文件后重新执行任务。

结论：任务未能进入可验收状态；本报告为草稿，依据 Acceptance 要求，最终报告需在批准后转正。

## Governance

This report was written only after human approval, under a Writer Lease, with an execution receipt and verification evidence.
