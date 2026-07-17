# NEXARA PROGRAM CONSTITUTION V1

> **Authority Declaration:** This Program Constitution is subordinate to the
> [NEXARA Sovereign Engineering Constitution (NSEC) V2.0](governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2.md),
> the single highest engineering governance source for this project.
> On any conflict, NSEC prevails. This declaration is machine-verified by
> `scripts/governance/validate_nsec.py` and must not be removed or altered
> without an NSEC-compliant amendment.

## 最高目标
构建完全第一方、非 Hermes 运行依赖、建立在 NEXARA PRIME 上的主权智能体。

## 不可变原则
1. Human sovereignty：用户拥有目标、批准、接管、撤销和最终责任。
2. Hermes runtime dependency = 0。Codex/Claude/Hermes 只可作为开发执行器。
3. Model independence：模型不拥有 Agent Identity、Mission、Memory、Policy 或 Evidence。
4. Runtime Truth：mock/dry-run/live 明确区分；无 E1/E2 不得 Completed。
5. Policy before capability；Single Writer；fail-closed；secret leakage=0。
6. Evolution 只能 Proposal → Simulation → Benchmark → Approval → Deploy → Rollback。

## 执行方式
- 读取本文件、NEXARA_DEVELOPMENT_GATES_V1.yaml 和 .nexara/GATE_STATUS.json。
- 自动选择依赖已满足且未 PASS 的最早 Gate。
- 在 Gate 内持续执行，直到 PASS、BLOCKED 或需要真实 R3/R4 人工批准。
- 每个 Gate 必须运行测试、生成 Evidence、更新状态、创建本地 commit、保持 worktree clean。
- 禁止 push / merge / tag / deploy / payment / external_send / destructive delete，除非用户明确批准。
- 禁止通过删除测试、降低断言、改报告文字、把 mock 说成 live 获得 PASS。

## 人类介入条件
只在以下情况请求用户：
1. 产品名/品牌/商业策略的不可逆决定。
2. R3/R4 外部副作用。
3. 不可恢复的数据迁移或破坏性变更。
4. 两个架构方案在现有证据下无法判定。
5. 生产发布、push、merge、tag、deploy。

## 最终产品边界
Platform = NEXARA PRIME。
First-party Agent = 名称待定，包 nexara_prime.agent。
External models/tools = replaceable resources。
Hermes/Codex/Claude = build-time executors only。
