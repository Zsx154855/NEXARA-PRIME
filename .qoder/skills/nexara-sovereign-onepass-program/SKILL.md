---
name: nexara-sovereign-onepass-program
description: >
  NEXARA-PRIME 第一方主权智能体的单技能连续交付协议。
  默认启用动态多分身、自动 Skills、Token 节省、单一写入者、
  根因修复、真实验证、证据更新、恢复续跑和自动 Program Loop。
  当在 NEXARA-PRIME 仓库中执行开发任务时自动应用。
version: 2.0.0
---

# NEXARA SOVEREIGN ONEPASS PROGRAM

## 项目身份

- Product: NEXARA PRIME
- Repository: `/Users/agentos/NEXARA-PRIME`
- Remote: `Zsx154855/NEXARA-PRIME`
- Runtime Agent: NEXARA 第一方主权智能体

Hermes、Claude、Codex、DeepSeek 和其他模型只作为开发执行器或可替换推理资源。禁止将它们引入为 NEXARA 产品运行时的强制依赖。AgentsOS 是历史资产或人类控制产品层，不是 NEXARA-PRIME 的 Runtime Truth Source。

---

## 权威来源 (优先级从高到低)

1. 用户当前明确指令
2. `NEXARA_PROGRAM_CONSTITUTION_V1.md`
3. `NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md`
4. `NEXARA_DEVELOPMENT_GATES_V1.yaml`
5. 当前 `PROGRAM_STATE` / `GATE_STATUS` / Evidence
6. 当前代码、测试、Git 状态和真实运行结果

禁止创建与这些文件竞争的第二套宪章、Gate 系统、状态系统或治理平台。

---

## 默认运行模式 (始终开启)

- Autonomous Continuous Mode
- Dynamic Multi-Agent Mode
- Relevant Skills Auto-Selection
- Token Saving Mode
- Runtime Truth Mode
- Single Writer Mode
- Evidence Mode
- Recovery Mode

不要求用户每轮重复开启。

---

## Program Loop (每轮必须执行)

1. 读取当前真实状态
2. 识别最早且最高价值的未完成项
3. 判断是否处于正确产品主线
4. 完整读取相关代码、测试、Review 和失败证据
5. 聚类根因
6. 冻结本轮 ChangeSet
7. 单批次实施
8. 运行验证阶梯
9. 更新现有状态与 Evidence
10. 清理本轮临时文件
11. 选择下一未完成项
12. 自动继续

完成一个局部任务后不得默认停止。只有遇到停止条件才可退出 Program Loop。

---

## 核心执行规则

### 项目身份锁
执行任何修改前必须检查: pwd、Git repository root、remote、branch、HEAD、worktree status、当前 Mission、当前权威状态文件。发现项目、remote 或任务身份错误时立即停止本轮写入。

### 现有工作保护
- 发现未提交或未跟踪内容时: 判断是否属于当前任务，识别是否可能由其他执行器生成，未确认所有权前禁止覆盖
- 禁止自动执行: `git reset`、`git restore`、`git clean`、`git stash`、`rm -rf`、覆盖/删除未知文件
- 不得丢失用户资料、Knowledge Universe、Chats、Secret、个人内容或已有 Evidence
- Chats 等非项目资产禁止提交

### 动态多分身
- 主控制器始终只有一个，同一工作区始终只有一个 Writer
- 简单任务: 仅主控制器
- 中等任务: 主控制器 + 只读审计分身 + Writer + 独立验证分身
- 高风险/跨域: 可动态启用 Architecture、Security、Runtime、Test、Evidence、Product/UI、Memory、Reviewer
- 分身只能获得完成职责所需的最小上下文
- 禁止多个 Writer 同时修改同一工作区，禁止为显示"多 Agent"而启动无实际收益的分身

### 自动 Skills 选择
优先复用已有 Skill、脚本、Runtime、测试和工具。禁止为当前任务重复创建已有系统或创建第二套 Scheduler、Recovery、CLI、Memory、Evidence、Policy Engine、SDO、治理平台。只有证明现有实现无法扩展时，才允许新增最小能力。

### 产品主线保护 (任务优先级)
1. 第一方 Agent Identity 与 Personality
2. Mission 真实闭环
3. Contract 与 Planning
4. Policy、Approval 与有限执行
5. Verification 与 Runtime Truth
6. Evidence 与 Audit
7. Memory 与知识系统
8. Strategy 与模型路由
9. Recovery 与连续运行
10. Evaluation 与受控演化
11. macOS 原生产品闭环
12. 独立 iPhone/iPad SwiftUI 产品

Web 默认只作为调试/远程控制/辅助界面。禁止长期停留在只写文档、只建治理、只做模拟、只做展示 UI、只做 Mock、只修旧项目、只增加框架但没有真实 Mission。

### 一次完整审计 (修改前)
必须一次性读取: 当前失败、Review Threads、相关代码、相关测试、API 与状态契约、依赖声明、工作区 Diff、最近真实日志、现有 Evidence。所有问题按根因聚类。属于同一根因/同一接口/同一安全边界的问题必须在同一批次解决。禁止看一条 Review 修一条、只修症状、为通过测试而修改错误断言、反复小补丁。

### 冻结 ChangeSet
开始写入前内部确定: 根因、修改文件、新增或修改的测试、兼容性影响、状态迁移、Evidence、回滚方式、验收命令。冻结后禁止无关重构。但如果验证证明根因位于依赖/CI/公共接口/共享 Runtime，可以在当前闭环内修复真正根因。

### 环境规则
只使用 NEXARA-PRIME 自己的项目环境和工具 (`.venv/bin/python`、项目现有 lockfile、现有构建与测试命令)。禁止使用 AgentsOS 或其他仓库的共享虚拟环境。禁止为临时通过测试不断执行随机依赖安装。

### 修复策略
- 第一轮实施必须针对根因完成整个批次
- 第一次失败: 分类为代码/测试/环境/平台/外部故障，重新定位根因，不立即做表面补丁
- 第二次失败: 自动进入 Recovery Mode，对本轮自己的变更进行 Diff 审计，必要时只回滚本轮自己的失败实现，选择不同实现策略，重新完整验证
- 同一根因连续两种策略均失败: 停止试错，保留原始证据，输出 BLOCKED，不破坏已有可用基线
- 禁止无限 retry 和同类 patch loop

### 验证阶梯 (按影响范围执行)
1. 语法、编译、类型检查
2. 当前问题专项测试
3. 当前模块回归测试
4. 直接依赖模块测试
5. 安全与权限边界测试
6. 重启、恢复或持久化测试
7. `git diff --check`
8. 状态与 Evidence 一致性检查
9. 全量基线测试

修改核心 Runtime、共享接口、状态机、Policy/Approval、Evidence/Memory、依赖、构建/CI 时必须运行全量测试。禁止只运行一个专项测试就声称整个项目通过。

### Runtime Truth
必须明确区分: `CODE_FAILURE`、`TEST_FAILURE`、`ENVIRONMENT_FAILURE`、`CI_PLATFORM_FAILURE`、`EXTERNAL_SERVICE_FAILURE`、`PERMISSION_BLOCK`、`NOT_EXECUTED`、`VERIFIED_PASS`。没有实际执行的测试不得标记 PASS。Mock/fixture/demo/deterministic provider 的结果必须明确标识。禁止 Magic PASS。

### Evidence 与现有状态
本轮涉及的真实输出必须保留: 执行命令、exit code、测试结果、构建结果、关键日志、Artifact 路径、SHA256 或现有哈希、Diff 摘要、状态变化、未解决阻塞。如果仓库已有 `PROGRAM_STATE`、`GATE_STATUS`、Evidence、Artifact Manifest、Checksum Manifest、SBOM、Release Notes，则必须同步更新相关项。禁止为记录状态再创建第二套 Evidence 或状态系统。

### 执行权限
默认允许连续执行: 本地读取、搜索和分析、调用相关 Skills、运行测试、编译和构建、生成本地 Evidence、可回滚代码修改、本地安全诊断、状态更新、清理本轮明确生成的临时文件。以下动作必须获得用户当前明确批准: `push`、`merge`、`tag`、`release`、`deploy`、`payment`、`external_send`、Secret 写入/输出/轮换、`sudo`、不可逆删除、权限提升、外部公开分发。

### 本地提交
只有满足以下条件时才能创建本地原子提交: 当前 Mission 明确允许、所有必需验证通过、Evidence 已生成、不包含未知修改/Secret/Chats/个人资料、Commit scope 与任务一致。本地提交不等于允许 push。禁止连续制造大量 fix/typo/test/review/temporary fix，优先一个完整原子提交。

### Token 节省规则
默认执行: Diff first、局部读取、不重复读取未变化文件、不重复解释用户已知背景、不输出私有推理过程、不为简单任务启动多个分身、分身只接收最小必要上下文、优先确定性命令而非长篇推理、优先修复根因而非多轮试错、已有报告只读取相关部分、不重复生成架构文档、不向用户提供多套选择题、在安全范围内自行选择最佳实现。需要汇报时只输出压缩后的事实和结论。

---

## 停止条件 (Program Loop 退出条件)

1. 需要 push、merge、tag、release 或 deploy 批准
2. 涉及付款、外发、Secret、sudo 或不可逆删除
3. 缺少无法从仓库和环境推导的关键输入
4. 外部服务或平台持续不可用
5. 同一根因两种独立策略均失败
6. 已完成当前批准范围内的最终交付
7. 用户明确要求停止

普通测试失败、编译错误、依赖问题、Review 意见和可回滚代码问题，不属于立即停止条件。

---

## 最终输出格式

每轮只输出一次结果:

```
NEXARA SOVEREIGN ONEPASS RESULT

status:          PASS | PARTIAL | FAIL | BLOCKED | HUMAN_APPROVAL_REQUIRED
project:         NEXARA-PRIME
mission:         <当前 Mission>
branch:          <当前分支>
head:            <HEAD commit>
root_causes:     <根因列表>
implementation:  <实施摘要>
files_changed:   <修改文件列表>
tests:           <测试结果>
runtime_truth:   <运行时真值状态>
security:        <安全检查结果>
evidence:        <Evidence 引用>
state_updated:   <状态更新摘要>
local_commit:    <本地 commit hash 或 N/A>
external_actions: <需要人工批准的外部动作>
remaining_blockers: <剩余阻塞项>
next_mission:    <下一个 Mission 或 N/A>
program_loop:    CONTINUE | STOPPED
```

禁止使用模糊表述如"应该可以""理论完成""基本完成""看起来正常""大概率通过"。

---

## 其他资源

- 完整执行协议与修复策略详见 [reference/execution-rules.md](reference/execution-rules.md)
- 仓库权威文件: `NEXARA_PROGRAM_CONSTITUTION_V1.md`、`NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md`、`NEXARA_DEVELOPMENT_GATES_V1.yaml`
- 运行时状态: `.nexara/PROGRAM_STATE.json`、`.nexara/GATE_STATUS.json`
