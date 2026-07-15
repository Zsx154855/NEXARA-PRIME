# 执行规则详解

本文档展开 SKILL.md 中压缩的核心规则，供主控制器在需要详细指导时查阅。

---

## 1. 项目身份锁 — 完整检查清单

执行任何修改前必须确认:

```bash
pwd                          # 必须在 /Users/agentos/NEXARA-PRIME
git remote -v                # origin = Zsx154855/NEXARA-PRIME
git branch --show-current    # 当前分支
git rev-parse HEAD           # 当前 HEAD
git status --porcelain       # worktree 状态
```

禁止因为终端当前停在其他仓库就自动把其他仓库当成当前主线。不得硬编码已经可能过期的 branch 或 HEAD。

---

## 2. 现有工作保护 — 详细规则

### 发现未提交或未跟踪内容时:

1. 判断是否属于当前任务
2. 识别是否可能由其他执行器生成
3. 在未确认所有权前禁止覆盖
4. 优先基于当前 Diff 继续
5. 只有发生真实冲突时才使用隔离 worktree

### 禁止自动执行:
- `git reset`
- `git restore`
- `git clean`
- `git stash`
- `rm -rf`
- 覆盖未知文件
- 删除未知 untracked 文件

### 不可丢失的资产:
用户资料、Knowledge Universe、Chats、Secret、个人内容、已有 Evidence

---

## 3. 动态多分身 — 触发条件

| 任务类型 | 分身配置 | 说明 |
|---------|---------|------|
| 简单任务 | 仅主控制器 | 单步、低风险、明确修改 |
| 中等任务 | 主控制器 + 只读审计 + Writer + 独立验证 | 多文件、跨模块 |
| 高风险/跨域 | 上述 + Architecture/Security/Runtime/Test/Evidence/Product/Memory/Reviewer | 按需动态启用 |

分身只能获得完成职责所需的最小上下文。禁止多个 Writer 同时修改同一工作区。

---

## 4. 自动 Skills 选择 — 禁止清单

禁止为了当前任务:
- 重复创建已有 Skill
- 创建第二套 Scheduler
- 创建第二套 Recovery
- 创建第二套 CLI
- 创建第二套 Memory
- 创建第二套 Evidence
- 创建第二套 Policy Engine
- 创建完整 SDO
- 创建新的治理平台

---

## 5. 一次完整审计 — 读取清单

修改前必须一次性读取:
1. 当前失败信息
2. Review Threads
3. 相关代码
4. 相关测试
5. API 与状态契约
6. 依赖声明
7. 工作区 Diff
8. 最近真实日志
9. 现有 Evidence

### 根因聚类规则:
- 属于同一根因/同一接口/同一安全边界的问题必须同一批次解决
- 禁止看一条 Review 修一条
- 禁止修完再等下一条
- 禁止只修症状
- 禁止为通过测试而修改错误断言
- 禁止反复小补丁
- 不属于当前根因且不会阻塞交付的问题可登记，但不得借机无限扩大范围

---

## 6. 冻结 ChangeSet — 内部确认项

开始写入前必须内部确定:
- 根因
- 修改文件列表
- 新增或修改的测试
- 兼容性影响
- 状态迁移
- Evidence 更新
- 回滚方式
- 验收命令

冻结后禁止无关重构。但验证证明根因位于依赖/CI/公共接口/共享 Runtime 时，可在当前闭环内修复真正根因。

---

## 7. 环境规则 — 详细说明

### 只使用:
- 项目 `.venv/bin/python`
- 项目已存在的 lockfile
- 项目现有构建与测试命令

### 禁止:
- 使用 AgentsOS 或其他仓库的共享虚拟环境
- 为临时通过测试不断执行随机依赖安装

### 依赖缺失时判断:
1. 依赖声明缺失
2. 锁文件漂移
3. 环境损坏
4. Python/Node/Swift 版本不匹配
5. 测试本身依赖未声明

修正后必须保证本地与 CI 使用相同依赖来源。

---

## 8. 修复策略 — 决策树

```
第一轮实施 (针对根因完成整个批次)
    │
    ├─ 成功 → 继续 Program Loop
    │
    └─ 失败
        │
        ├─ 第一次失败
        │   ├─ 分类: 代码/测试/环境/平台/外部故障
        │   ├─ 重新定位根因
        │   └─ 不立即做表面补丁
        │
        ├─ 第二次失败
        │   ├─ 自动进入 Recovery Mode
        │   ├─ 对本轮自己的变更进行 Diff 审计
        │   ├─ 必要时只回滚本轮自己的失败实现
        │   ├─ 选择不同实现策略
        │   └─ 重新完整验证
        │
        └─ 同一根因连续两种策略均失败
            ├─ 停止继续试错
            ├─ 保留原始证据
            ├─ 输出 BLOCKED
            └─ 不破坏已有可用基线
```

---

## 9. 验证阶梯 — 触发全量测试的条件

以下情况必须运行全量测试:
- 修改核心 Runtime
- 修改共享接口
- 修改状态机
- 修改 Policy 或 Approval
- 修改 Evidence 或 Memory
- 修改依赖
- 修改构建或 CI
- 准备本地原子提交
- 准备 merge-ready 状态

禁止只运行一个专项测试就声称整个项目通过。

---

## 10. Runtime Truth — 状态值定义

| 状态 | 含义 |
|------|------|
| CODE_FAILURE | 代码逻辑错误 |
| TEST_FAILURE | 测试断言失败 |
| ENVIRONMENT_FAILURE | 环境配置/依赖问题 |
| CI_PLATFORM_FAILURE | CI 平台问题 (无 Runner 等) |
| EXTERNAL_SERVICE_FAILURE | 外部服务不可用 |
| PERMISSION_BLOCK | 权限不足 |
| NOT_EXECUTED | 未实际执行 |
| VERIFIED_PASS | 已验证通过 |

关键约束:
- 没有实际执行的测试不得标记 PASS
- 历史测试数量不得冒充当前测试结果
- 平台没有分配 Runner 时不得说代码测试失败
- Mock/fixture/demo/deterministic provider 结果必须明确标识
- 不得冒充真实 Provider 或真实外部执行
- 禁止 Magic PASS

---

## 11. Evidence — 需保留的输出

本轮涉及的真实输出必须保留:
- 执行命令
- exit code
- 测试结果
- 构建结果
- 关键日志
- Artifact 路径
- SHA256 或现有哈希
- Diff 摘要
- 状态变化
- 未解决阻塞

二进制产物可留在 ignored `dist`，但必要的生成记录、Manifest、Checksum 和 Evidence 必须可追溯。

---

## 12. 执行权限 — 完整清单

### 默认允许 (连续执行):
- 本地读取
- 搜索和分析
- 调用相关 Skills
- 运行测试
- 编译和构建
- 生成本地 Evidence
- 可回滚代码修改
- 本地安全诊断
- 状态更新
- 清理本轮明确生成的临时文件

### 必须用户明确批准:
- `push`
- `merge`
- `tag`
- `release`
- `deploy`
- `payment`
- `external_send`
- Secret 写入、输出或轮换
- `sudo`
- 不可逆删除
- 权限提升
- 外部公开分发

---

## 13. 本地提交 — 条件清单

### 必须满足:
1. 当前 Mission 明确允许本地提交
2. 所有必需验证通过
3. Evidence 已生成
4. 不包含未知修改
5. 不包含 Secret
6. 不包含 Chats 或个人资料
7. Commit scope 与任务一致

### 禁止:
- 连续制造大量 `fix again`/`typo fix`/`test fix`/`review fix`/`temporary fix`
- 优先一个完整原子提交

---

## 14. Token 节省规则 — 完整清单

- Diff first
- 局部读取
- 不重复读取未变化文件
- 不重复解释用户已知背景
- 不输出私有推理过程
- 不持续播报每一步
- 不为简单任务启动多个分身
- 分身只接收最小必要上下文
- 优先确定性命令而非长篇推理
- 优先修复根因而非多轮试错
- 已有报告只读取相关部分
- 不重复生成架构文档
- 不向用户提供多套选择题
- 在安全范围内自行选择最佳实现

---
