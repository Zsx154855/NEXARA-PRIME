# NEXARA-PRIME × OpenMausBot — AEP-03 一次性 Mac 接管任务包

> 任务类型：真实工程实验；**本文件是交给已授权的 Mac 本地 Agent / Codex / OpenMinis 的执行指令，不是 Mac 已执行的证明。**
>
> 截止提交时 GitHub：PR #57=`96d7628d69413a244d83bbe59ef143f5ab11a4bb` → main；PR #58=`f994e06a2c3897f4b7ca48ca4f71a281e06389c8` → PR #57。运行前重新查 HEAD，如果不同必须重新冻结。
>
> 工程范围仅 `Zsx154855/NEXARA-PRIME`。**BLACK FACTORY/UNSEEN 不在此次范围。**

## 0. 角色与执行权

你是 AEP-03 本机一次性工程总控。不要停留在计划。执行前检查当前项目实际路径、Git HEAD、dirty worktree、Mac Bridge 版本、OpenMausBot 服务、CLI 参数及模型费用。不得覆盖本机已修改文件、改变生产配置、访问私人项目或秘密、启用永久服务、产生新增付费模型调用或合并主线。

**思考无需审批。** 在预先授权的隔离实验目录中自主研究、写合成代码、测试、修复及创建临时 Agent；仅外部高影响行为依旧遵守既有授权。一个实验目录同一时刻只允许一个 Writer。不得因小规模工程步骤反复请 MASTER 继续。

Skills：先通过本机真实 Skills 发现接口查找并按需激活“持续自主研发总控”“受控执行器与故障恢复”“智能体能力评测”“HTML 图解回答”、Token/Context 管理；对每个技能记录调用入口、版本/SHA、返回值与任务阶段。不可访问则 `SKILL_ACCESS_BLOCKED`，采用本指令等效流程，不能将 GitHub 操作冒称 Skill 激活。采用增量检索和最小上下文，严格区分模型声明与工具证据。

## 1. Gate A：项目与真实环境预检

在 Mac 的真实工程仓库之外创建本轮唯一临时工作根目录，以下为示例，按实际唯一目录调整：

```bash
export REPO=/path/to/current/NEXARA-PRIME
export LAB="$HOME/Downloads/AEP03_LAB_20261108"
python3 aep03_local_gate.py probe --repo "$REPO" --out "$LAB-preflight.json"
```

`probe` **不启动模型、不会安装 OpenMausBot、不会修改项目**。必须核实真实 CLI 版本、`openmausbot help run`, `openmausbot help wait`, `openmausbot doctor --json --url http://127.0.0.1:8799`；如果 CLI 不存在或服务器不在线，标记 `LIVE_EXECUTION_BLOCKED`，不要用假 CLI 替代。

检查 `git status --porcelain`；原始工作树若 dirty，**严禁重置、清理、覆盖**。从已有对象或经过授权的只读 `git fetch` 创建三个独立工作树，检验 #57 祖先与 #58 SHA，所有测试数据和修改在独立目录。不要擅自创建永久 LaunchAgent 或启动通用后台服务。OpenMausBot 可能与 OpenMinis 同时存在；先查端口、进程拥有者和数据目录，禁止杀掉其他服务。

针对 main、PR #57、PR #58 在**同一 Python/pytest 环境和隔离配置**下运行聚焦测试与全量回归；失败保留原始 stdout/stderr/exit/hash。旧 #53/#54/#55 的共同六失败来自 [Issue #56](https://github.com/Zsx154855/NEXARA-PRIME/issues/56)，不能自动判定为这两个新 PR 的回归或直接忽略。

## 2. Gate B：创建真实合成项目并运行三 Agent

```bash
python3 aep03_local_gate.py seed --root "$LAB"
python3 aep03_local_gate.py verify --project "$LAB/task_a" --phase baseline --out "$LAB/evidence/task_a_pre.json" || true
python3 aep03_local_gate.py verify --project "$LAB/task_b_control" --phase baseline --out "$LAB/evidence/task_b_control_pre.json" || true
python3 aep03_local_gate.py verify --project "$LAB/task_b_memory" --phase baseline --out "$LAB/evidence/task_b_memory_pre.json" || true
```

三个仓库包含真实的、可复现的 Python 代码缺陷和不可改写的客观测试。`task_a` 是逗号分隔事件标签规范化；`task_b_*` 是管道分隔技能代码规范化。各仓库有独立 Git 基线。测试必须先真实失败；缺陷不从 NEXARA 主工程注入。

在现有 OpenMausBot 环境中配置独立 **Lead（可选）＋ Researcher ＋ Engineer ＋ Independent QA**。Lead 负责委派，不能代替三个实际执行角色。每位 Agent 要读取自己的 SKILL.md/能力索引，记录真实使用；Researcher 只读调查并提交根因记录，Engineer 仅修改本轮合成工作树，QA 必须以独立 Agent 身份审查 diff 并实际重新运行测试。配置一次性的明确可用且经核实为**零新增费用**的引擎；如只能使用可能收费的远端模型，停止并标记 `MODEL_COST_BLOCKED`。不能用 Claude/Codex/DeepSeek 的假 Bot 名称或预设任务树冒充三个真实运行者。

**任务接线：** 先由 NEXARA 实际 `AutonomousGoalLoop.tick` 处理 `task_a` 的真实测试失败事件并持久化真实提案 ID。该机制当前只会生成 `fix_failing_tests` 的 R0 只读建议；要实现“修改合成代码”必须由 NEXARA 现有 Mission/Kernel 以本轮既有授权产生相应执行任务，绝不能暗中把只读提案当作写入许可。不要伪造 AEP-01 示例 JSON 充当真实认知产生的提案。若连接不上该任务编译/授权入口，Gate E=`PARTIAL/BLOCKED`，不得宣称全闭环。

为每项任务使用**全新且专用的真实 OpenMausBot conversation/thread**，避免旧消息干扰。`openmausbot run ... --wait none --send-id ...` 必须返回真实 `threadId`、`since`、`at`、`messageId`、`sendId`；使用 AEP-02 既有脚本（位于 PR #58）：

```bash
PYTHONPATH=src python scripts/proofs/openmausbot_execution_proof.py submit \
  --db "$LAB/evidence/mission-ledger.db" \
  --proposal-json "$LAB/evidence/actual-nexara-proposal.json" \
  --bot-id "$ACTUAL_LEAD_BOT_ID" --thread-id "$ACTUAL_DEDICATED_THREAD_ID"
PYTHONPATH=src python scripts/proofs/openmausbot_execution_proof.py resume \
  --db "$LAB/evidence/mission-ledger.db" --mission-id "$ACTUAL_NEXARA_MISSION_ID"
```

上面的 `proposal-json` 必须是 NEXARA **实际**输出的、可追溯的记录；`bot-id`、`thread-id` 必须来自实时 OpenMausBot，不得造假。执行前校验当前 CLI 是否真的支持 `--wait none`, `--since`, `--strict` 及 JSON 结构（官方版本与实际安装版本不保证一致）。原始 CLI/Agent 终端输出仅留本地。断线 `wait` 需使用固定 `--since` 和同一 `send_id` 恢复；状态 `REPORTED` 不是 QA PASS。

## 3. Gate C/D：真实恢复与独立验收

- **Gate C**：逐项检查 Mission/Thread/Bot ID、任务树 parentId、所有真实子节点结算状态、工具调用摘要、修复 diff、退出码、真实时间与日志 hash。任何子任务仍 running 或 failed/cancelled，不能升级为完成。
- **Gate D**：只终止本轮**适配器**测试进程，不终止他人 Agent 进程。对同一 Mission 实际注入：提交后客户端退出、wait 客户端断开、服务不可达、重启 Python 适配器、重复 resume、老回执注入。外部服务不可达只能记录并等待恢复，不能谎称已经执行了真实 Agent。整机重启仅出方案、不执行。
- 先记录独立 QA Agent 的身份、review 对话/线程、原始测试命令及退出码，再由另一个独立 OS subprocess 执行：

```bash
python3 aep03_local_gate.py verify --project "$LAB/task_a" --phase qa --out "$LAB/evidence/task_a_qa.json"
```

`verify` 拒绝改动初始测试文件，生成新日志及 SHA256，且不会把 OS 测试进程冒称 Independent QA Agent。Python 进程的环境变量已降到最小，但**不是 OS/VM 沙盒**；执行 AI 修改过的代码前，本地总控必须确认在无私人资料的隔离账户/VM 中运行，或停止 Gate B/C/D。只要独立 QA、代码差异或真实任务树缺一项，则 Gate B/C/D 不能 PASS。

## 4. Gate E：验证过的经验写入和迁移，不造第二套记忆

使用当前真实 `src/nexara_prime/brain/experience_learner.py::ExperienceLearner` 与 `memory_controller.py::MemoryController`，而不是创建第二套 Learning DB。

1. QA 真正通过后，通过既有 `EvidenceStore.add(... actor=auditor_id, trace_id=..., idempotency_key=...)` 提交真实测试日志摘要及固定 SHA 的可校验证据，再按真实契约 `verify`；拒绝模型自述。
2. 在相同认知存储实例上调用 `ExperienceLearner.record_outcome(..., evidence_id=real_verified_id)` 和 `record_lesson(...)`，保留来源、适用条件及失败边界；跨进程重新读取并调用 `rank_experiences` 或 `get_lessons`。记忆写入成功≠经验迁移。
3. B-control 不检索 A 的经验；B-memory **必须**实际调用检索入口，记录查询、命中 Memory ID、适用性判断与引用；两个 B 分支不能共享任务上下文、未授权代码补丁和运行历史。
4. 比较双方真实测试结果、真实 Agent 工具调用次数、模型 Token/费用（没有提供就标 `NOT_VERIFIED`，不要估算为 0）、是否重复问用户、修复质量与可恢复性。一次样本只证明一次迁移，不证明普遍效益。
5. `EvidenceGatedLearning.evaluate` 当前要求同一 mission_id、同一 suite_id 和严格下降的 Token；不要把 Task A、B 的跨任务实验硬塞到同一指标比较，也不要制造 Token 计数。需要时记录跨任务经验评估为 `PARTIAL`，在真实证据出现后提出最小兼容扩展。

## 5. 原始证据与检查点

在本机私有目录中保留 `preflight.json`、三个合成仓库及其原始 Git HEAD、`mission-ledger.db`、原始 OpenMausBot JSON/CLI 退出码、真实任务树、各 Agent 运行日志、补丁与审计 SHA、独立 QA、跨重启恢复与经验检索回执、调用与费用信息。本机记录全量，**公开 GitHub 只写经过脱敏的摘要**。

任何异常必须明确归类 `BLOCKED` / `PARTIAL` / `FAIL` / `NOT_VERIFIED` / `PASS`。不得假装 Mac Bridge v0.3 的 `diagnose_gate0_logs` 已有权限执行 AEP03；它只是固定历史日志诊断工具。没有新的本地显式接线前，不能把 GitHub Issue 留言当作可执行远控指令。

**停止条件**：没有真实 OpenMausBot 服务、没有能合法零新增费用运行的模型、没有隔离执行环境、没有真实 Agent 调用能力，或缺少关键证据。无须反复请求“继续”；在本机可执行范围中完成能够独立完成的任务，最后交出失败/通过证据与具体下一项待授权动作。

## 6. 五门槛验收枚举

| Gate | 唯一 PASS 条件 |
|---|---|
| A | 最新完整仓库的 Mac 原生测试与基线差异经核验 |
| B | 真实 OpenMausBot 实际调动三名 Agent，证据包括独立 QA 的实际工具输出 |
| C | CLI 任务关联、完整子任务树、独立验收数据均真实可核验 |
| D | 在本轮专属进程与工作目录中完成可重复的重启/断线/去重实验 |
| E | 实际经验产生、经 QA 关联写入、跨会话检索并在任务 B 中使用，与基线比较 |

任务结束须分别输出五项状态、固定 SHA/环境/时间、实际命令与退出码、日志 hash、费用与 Token（缺失则 NOT_VERIFIED）、缺口、Draft PR 链接及 Git 主线未合并证明。