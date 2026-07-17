---
name: nexara-sovereign-onepass-program
description: >
  NEXARA-PRIME 第一方主权智能体的单文件连续交付协议。
  在 NEXARA-PRIME 中执行开发、修复、验证、恢复、状态更新或连续 Program Loop 时使用。
  默认启用动态多分身、相关 Skills 自动选择、Token 节省、单一写入者、
  根因修复、Runtime Truth、Evidence、恢复续跑和人类主权边界。
version: 2.0.0
---

# NEXARA SOVEREIGN ONEPASS PROGRAM SKILL

## 0. 唯一目标

当前唯一主项目是：

- Product：NEXARA PRIME
- Repository：`/Users/agentos/NEXARA-PRIME`
- Remote：`Zsx154855/NEXARA-PRIME`
- Runtime Agent：NEXARA 第一方主权智能体

Hermes、Claude、Codex、DeepSeek 和其他模型只作为开发执行器或可替换推理资源。

禁止将它们引入为 NEXARA 产品运行时的强制依赖。

AgentsOS 是历史资产或人类控制产品层，不是 NEXARA-PRIME 的 Runtime Truth Source。

除非用户当前明确指定 AgentsOS，否则禁止自动进入或修改 AgentsOS 仓库。

创建、修正或安装本 Skill 只代表一个局部 Mission 完成，不代表 NEXARA Program 完成。

---

## 1. 权威来源

执行前按以下优先级读取真实约束：

1. 用户当前明确指令
2. `governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md` (NSEC — 最高工程治理源)
3. `governance/authority_index.yaml` (Authority Index)
4. `NEXARA_PROGRAM_CONSTITUTION_V1.md`
5. `NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md`
6. `NEXARA_DEVELOPMENT_GATES_V1.yaml`
7. 当前 `PROGRAM_STATE` / `GATE_STATUS` / Evidence
8. 当前代码、测试、Git 状态和真实运行结果

禁止创建与这些文件竞争的第二套宪章、Gate 系统、状态系统或治理平台。

Gate 仅作为内部验收标准，不作为频繁停止和向用户反复申请确认的理由。

当通用 Skill 规范、执行器默认习惯与用户明确要求冲突时，以本节优先级为准。

NSEC 是唯一最高工程治理源。所有 Agent 入口、Skill、Contract 和 CI 必须绑定 NSEC canonical 路径与版本。禁止将 NSEC 全文复制到多个入口——只能引用 canonical source 并验证版本。

---

## 2. 默认运行模式

以下模式始终默认开启：

- Autonomous Continuous Mode
- Dynamic Multi-Agent Mode
- Relevant Skills Auto-Selection
- Token Saving Mode
- Runtime Truth Mode
- Single Writer Mode
- Evidence Mode
- Recovery Mode

不要求用户每轮重复开启。

所有必要执行规则必须包含在本 `SKILL.md` 内。

不得依赖 reference 文件才能获得停止条件、权限边界、恢复策略、验证规则或 Program Loop 核心语义。

---

## 3. 项目身份锁

执行任何修改前，必须检查：

- `pwd`
- Git repository root
- remote
- branch
- HEAD
- worktree status
- 当前 Mission
- 当前权威状态文件

发现项目、remote 或任务身份错误时，立即停止本轮写入，并输出真实身份差异。

禁止因为终端当前停在其他仓库，就自动把其他仓库当成当前主线。

不得硬编码已经可能过期的 branch 或 HEAD；必须读取当前远端和本地真实值。

HEAD 必须报告真实 commit SHA，不得在 Git 仓库中无故写作 `N/A`。

---

## 4. 现有工作保护

发现未提交或未跟踪内容时：

1. 判断是否属于当前任务；
2. 识别是否可能由其他执行器生成；
3. 在未确认所有权前禁止覆盖；
4. 优先基于当前 Diff 继续；
5. 只有发生真实冲突时才使用隔离 worktree。

禁止自动执行：

- `git reset`
- `git restore`
- `git clean`
- `git stash`
- `rm -rf`
- 覆盖未知文件
- 删除未知 untracked 文件

不得丢失用户资料、Knowledge Universe、Chats、Secret、个人内容或已有 Evidence。

Chats 等非项目资产禁止提交。

通过远端连接器修改仓库时，也必须先读取目标文件 SHA，并避免覆盖未知并发修改。

---

## 5. 动态多分身，而不是固定堆 Agent

主控制器始终只有一个。

同一工作区始终只有一个 Writer。

根据任务自动启用分身：

### 简单任务

仅使用主控制器执行，不启动额外分身。

### 中等任务

可启用：

- 一个只读审计分身；
- 一个 Writer；
- 一个独立验证分身。

### 高风险或跨域任务

可动态启用：

- Architecture
- Security
- Runtime
- Test
- Evidence
- Product/UI
- Memory
- Reviewer

分身只能获得完成职责所需的最小上下文。

禁止多个 Writer 同时修改同一工作区。

禁止为了显示“多 Agent”而启动没有实际收益的分身。

---

## 6. 自动 Skills 选择

主控制器必须自动选择当前任务需要的既有 Skills。

优先复用已有 Skill、脚本、Runtime、测试和工具。

禁止为了当前任务：

- 重复创建已有 Skill；
- 创建第二套 Scheduler；
- 创建第二套 Recovery；
- 创建第二套 CLI；
- 创建第二套 Memory；
- 创建第二套 Evidence；
- 创建第二套 Policy Engine；
- 创建完整 SDO；
- 创建新的治理平台。

只有证明现有实现无法扩展时，才允许新增最小能力。

创建 Skill 时，通用的渐进披露建议不得覆盖用户明确要求的单文件权威协议。

---

## 7. Program Loop

每轮必须执行以下闭环：

1. 读取当前真实状态；
2. 识别最早且最高价值的未完成项；
3. 判断是否处于正确产品主线；
4. 完整读取相关代码、测试、Review 和失败证据；
5. 聚类根因；
6. 冻结本轮 ChangeSet；
7. 单批次实施；
8. 运行验证阶梯；
9. 更新现有状态与 Evidence；
10. 清理本轮明确生成的临时文件；
11. 选择下一未完成项；
12. 自动继续。

完成一个局部任务后不得默认停止。

局部 Mission PASS 后必须重新读取 `PROGRAM_STATE`、`GATE_STATUS` 和 Evidence，再选择下一 Mission。

只有遇到本 Skill 定义的停止条件才可以退出 Program Loop。

当当前状态已经到达人类主权边界时，必须准确输出 `HUMAN_APPROVAL_REQUIRED`，不得为了“继续”而虚构新的工程任务。

---

## 8. 产品主线保护

在选择下一任务时，优先级为：

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

Web 默认只作为调试、远程控制或辅助界面，不自动升级为主产品。

禁止长期停留在：

- 只写文档；
- 只建治理；
- 只做模拟；
- 只做展示 UI；
- 只做 Mock；
- 只修旧项目；
- 只增加框架但没有真实 Mission。

---

## 9. 一次完整审计

修改前必须一次性读取：

- 当前失败；
- Review Threads；
- 相关代码；
- 相关测试；
- API 与状态契约；
- 依赖声明；
- 工作区 Diff；
- 最近真实日志；
- 现有 Evidence。

所有问题必须按根因聚类。

属于同一根因、同一接口或同一安全边界的问题必须在同一批次解决。

禁止：

- 看一条 Review 修一条；
- 修完再等下一条；
- 只修症状；
- 为通过测试而修改错误断言；
- 反复小补丁。

不属于当前根因且不会阻塞交付的问题可以登记，但不得借机无限扩大范围。

---

## 10. 冻结 ChangeSet

开始写入前，在内部确定：

- 根因；
- 修改文件；
- 新增或修改的测试；
- 兼容性影响；
- 状态迁移；
- Evidence；
- 回滚方式；
- 验收命令。

冻结后禁止无关重构。

但如果验证证明根因位于依赖、CI、公共接口或共享 Runtime，可以在当前闭环内修复真正根因，不得因为机械范围限制而继续打补丁。

---

## 11. 环境规则

只使用 NEXARA-PRIME 自己的项目环境和项目工具。

优先使用：

- 项目 `.venv/bin/python`
- 项目已存在的 lockfile
- 项目现有构建与测试命令

禁止使用 AgentsOS 或其他仓库的共享虚拟环境。

禁止为了临时通过测试不断执行随机依赖安装。

依赖缺失时必须判断：

- 依赖声明缺失；
- 锁文件漂移；
- 环境损坏；
- Python/Node/Swift 版本不匹配；
- 测试本身依赖未声明。

修正后必须保证本地与 CI 使用相同依赖来源。

---

## 12. 修复策略

第一轮实施必须针对根因完成整个批次。

出现失败时：

### 第一次失败

- 分类为代码、测试、环境、平台或外部故障；
- 重新定位根因；
- 不立即做表面补丁。

### 第二次失败

- 自动进入 Recovery Mode；
- 对本轮自己的变更进行 Diff 审计；
- 必要时只回滚本轮自己的失败实现；
- 选择一条不同的实现策略；
- 重新完整验证。

### 同一根因连续两种策略均失败

- 停止继续试错；
- 保留原始证据；
- 输出 `BLOCKED`；
- 不破坏已有可用基线。

禁止无限 retry 和同类 patch loop。

---

## 13. 验证阶梯

为了节省 Token 和时间，不是每次都盲目运行所有测试。

按照影响范围执行：

1. 语法、编译、类型检查；
2. 当前问题专项测试；
3. 当前模块回归测试；
4. 直接依赖模块测试；
5. 安全与权限边界测试；
6. 重启、恢复或持久化测试；
7. `git diff --check`；
8. 状态与 Evidence 一致性检查；
9. 全量基线测试。

出现以下情况时必须运行全量测试：

- 修改核心 Runtime；
- 修改共享接口；
- 修改状态机；
- 修改 Policy 或 Approval；
- 修改 Evidence 或 Memory；
- 修改依赖；
- 修改构建或 CI；
- 准备本地原子提交；
- 准备 merge-ready 状态。

禁止只运行一个专项测试就声称整个项目通过。

对于纯声明式 Skill 修改，至少必须执行：

- YAML frontmatter 解析；
- name、description、version 检查；
- 0–21 全部章节存在性检查；
- 必要规则不依赖 reference 文件检查；
- 停止条件和权限边界检查；
- 输出枚举检查；
- UTF-8 和 Markdown 基本结构检查；
- 文件 SHA256；
- 仓库可用时执行 `git diff --check`；
- Qoder/目标执行器可用时执行 Skill 可发现性和最小行为场景验证。

Qoder/目标执行器不可用时，必须将行为验证标记为 `NOT_EXECUTED`，不得把静态验证冒充行为验证。

---

## 14. Runtime Truth

必须明确区分：

- `CODE_FAILURE`
- `TEST_FAILURE`
- `ENVIRONMENT_FAILURE`
- `CI_PLATFORM_FAILURE`
- `EXTERNAL_SERVICE_FAILURE`
- `PERMISSION_BLOCK`
- `NOT_EXECUTED`
- `VERIFIED_PASS`

没有实际执行的测试不得标记 PASS。

历史测试数量不得冒充当前测试结果。

平台没有分配 Runner 时，不得说代码测试失败。

Mock、fixture、demo 和 deterministic provider 的结果必须明确标识，不得冒充真实 Provider 或真实外部执行。

禁止 Magic PASS。

静态文件验证、行为验证、项目测试和外部服务验证必须分别报告。

---

## 15. Evidence 与现有状态

本轮涉及的真实输出必须保留：

- 执行命令；
- exit code；
- 测试结果；
- 构建结果；
- 关键日志；
- Artifact 路径；
- SHA256 或现有哈希；
- Diff 摘要；
- 状态变化；
- 未解决阻塞。

如果仓库已有：

- `PROGRAM_STATE`
- `GATE_STATUS`
- Evidence
- Artifact Manifest
- Checksum Manifest
- SBOM
- Release Notes

则必须同步更新本轮真正相关的项。

禁止为了记录状态再创建第二套 Evidence 或状态系统。

状态没有发生变化时，不得为了制造“已更新”而改写状态文件；应在 Evidence 中记录 `state_change: none` 及原因。

二进制产物可以留在 ignored `dist`，但必要的生成记录、Manifest、Checksum 和 Evidence 必须可追溯。

聊天中的文件树、文字说明或“见下方结构”不等于落盘 Evidence。

---

## 16. 执行权限

默认允许连续执行：

- 本地读取；
- 搜索和分析；
- 调用相关 Skills；
- 运行测试；
- 编译和构建；
- 生成本地 Evidence；
- 可回滚代码修改；
- 本地安全诊断；
- 状态更新；
- 清理本轮明确生成的临时文件。

以下动作必须获得用户当前明确批准：

- push
- merge
- tag
- release
- deploy
- payment
- external_send
- Secret 写入、输出或轮换
- sudo
- 不可逆删除
- 权限提升
- 外部公开分发

普通本地工程动作不得频繁打断用户。

通过 GitHub Contents API、连接器或其他远端写入方式产生 commit，同样属于远端写入，必须有用户当前明确授权。

---

## 17. 本地提交

只有满足以下条件时才能创建本地原子提交：

- 当前 Mission 明确允许本地提交；
- 所有必需验证通过；
- Evidence 已生成；
- 不包含未知修改；
- 不包含 Secret；
- 不包含 Chats 或个人资料；
- Commit scope 与任务一致。

本地提交不等于允许 push。

禁止连续制造大量：

- fix again
- typo fix
- test fix
- review fix
- temporary fix

优先一个完整原子提交。

连接器受限而无法一次提交多个文件时，必须在 Evidence 中如实记录，不得声称原子提交。

---

## 18. Token 节省规则

默认执行：

- Diff first；
- 局部读取；
- 不重复读取未变化文件；
- 不重复解释用户已知背景；
- 不输出私有推理过程；
- 不持续播报每一步；
- 不为简单任务启动多个分身；
- 分身只接收最小必要上下文；
- 优先确定性命令而非长篇推理；
- 优先修复根因而非多轮试错；
- 已有报告只读取相关部分；
- 不重复生成架构文档；
- 不向用户提供多套选择题；
- 在安全范围内自行选择最佳实现。

需要汇报时，只输出压缩后的事实和结论。

---

## 19. 停止条件

Program Loop 只能在以下情况停止：

1. 需要 push、merge、tag、release 或 deploy 批准；
2. 涉及付款、外发、Secret、sudo 或不可逆删除；
3. 缺少无法从仓库和环境推导的关键输入；
4. 外部服务或平台持续不可用；
5. 同一根因两种独立策略均失败；
6. 已完成当前批准范围内的最终交付；
7. 用户明确要求停止。

普通测试失败、编译错误、依赖问题、Review 意见和可回滚代码问题，不属于立即停止条件。

“局部文件创建完成”“报告已生成”“当前专项测试通过”都不属于 Program 完成条件。

---

## 20. 最终输出

每一轮只输出一次结果：

```text
NEXARA SOVEREIGN ONEPASS RESULT

status:
project:
mission:
branch:
head:
root_causes:
implementation:
files_changed:
tests:
runtime_truth:
security:
evidence:
state_updated:
local_commit:
external_actions:
remaining_blockers:
next_mission:
program_loop:
```

`status` 只能使用：

- `PASS`
- `PARTIAL`
- `FAIL`
- `BLOCKED`
- `HUMAN_APPROVAL_REQUIRED`

`program_loop` 只能使用：

- `CONTINUING`
- `HUMAN_APPROVAL_REQUIRED`
- `BLOCKED`
- `FINAL_DELIVERY_COMPLETED`

`head` 必须是真实 SHA。

`tests` 必须区分静态验证、行为验证、项目测试和未执行项。

`runtime_truth` 只能报告实际执行结果。

`evidence` 必须提供真实路径、记录或可验证引用。

`next_mission` 只能在 `FINAL_DELIVERY_COMPLETED`，或因真实阻塞无法确定后续任务时为 `N/A`；否则必须给出下一 Mission 或明确的人类审批动作。

禁止使用：

- 应该可以
- 理论完成
- 基本完成
- 看起来正常
- 大概率通过

禁止使用 `STOPPED` 表示局部 Mission 完成。

---

## 21. 核心执行原则

主线优先，不跨项目。

一个主控制器，一个 Writer，动态多分身。

多分身能力默认开启，但不浪费 Token。

相关 Skills 自动启用，不让用户重复选择。

先完整审计，再一次修改。

修根因，不修症状。

不创建第二套系统。

不使用共享污染环境。

不覆盖未知工作。

不做 Mock 或 Magic PASS。

本地安全动作连续执行。

外部后果动作等待人类批准。

完成一轮后自动进入下一轮。

直到真正交付，而不是直到生成一份报告。

当真实项目状态已经到达 push、tag、release、外部凭据或不可逆产品决策边界时，应停止在 `HUMAN_APPROVAL_REQUIRED`，这是正确履行人类主权，不是 Program Loop 失败。
