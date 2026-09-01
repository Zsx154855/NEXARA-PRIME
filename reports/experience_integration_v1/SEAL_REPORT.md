# Experience Integration V1 — SEAL REPORT

日期：2026-08-31
范围：NEXARA-PRIME ↔ NEXARA-PRODUCT 体验层对接（Experience API V1.0）

## 1. 交付内容

**NEXARA-PRIME（3e07318 → 2a6799a，8 个提交；本报告修订提交为最终封存）**
- `src/nexara_prime/experience_api.py`：V1.0 契约适配层。九个端点
  （/v1/user、/v1/session、/v1/conversations、/v1/agents*、/v1/missions、
  /v1/memories、/v1/evaluations*、/v1/token/usage、/v1/system/status，*为预留，
  返回 data: null），四字段信封、27 态任务状态→4 态映射、12 类记忆→3 类映射、
  中文相对时间。挂载于 `create_app()`。
- `tests/test_experience_api.py`：14 个契约测试（信封、分页、状态映射、空库、
  角色映射、时间戳健壮性、运行时长分支）。
- `scripts/seed_experience_demo.py`：端到端演示种子脚本（HTTP 注入）。

**NEXARA-PRODUCT（45bb5b2 → 0ff2afd，10 个提交）**
- Shared 包：`NexaraExperienceAPI` 协议、`NexaraEnvelope` 信封、
  `NexaraMockExperienceAPI`、`NexaraLiveAPI`（URLSession）、
  `NexaraExperienceStore`（@Observable，失败可重试）、`NexaraExperienceProvider`
  （NEXARA_RUNTIME_BASE 环境切换）、`NexaraLoadingView`。21 个测试全绿。
- macOS：五视图经 Store 取数，零 Mock 直调；控制台连接状态标识；
  AppKit 窗口注入（MainActor.assumeIsolated）。selftest 通过。
- iOS：五 Tab 对等改造（外壳 + 内容结构体），xcodebuild BUILD SUCCEEDED。

## 2. 测试结果

| 项 | 结果 |
|---|---|
| PRIME experience_api 测试 | 14 passed |
| PRIME 全量套件 | 2073 passed / 5 failed（均为预存环境性失败，见附注） |
| ruff（本次改动文件） | clean |
| secret scan（本次改动文件） | 0 findings |
| PRODUCT Shared swift test | 21 passed |
| macOS swift build | Build complete（零警告） |
| iOS xcodebuild | BUILD SUCCEEDED |
| macOS selftest（Mock 模式） | exit 0 |

附注：全量套件中 `tests/test_receipt_self_reference.py` 的失败要求干净 worktree，
由仓库预存脏状态触发（2930 个 .derivedData 缓存删除 + .nexara 状态文件修改），
与本次改动无关（本次未触碰任何 receipt 相关代码）。

## 3. 契约自查（契约 §9）

- [x] 字段名与 Shared 包模型属性名一致（逐模型核对 Models.swift）
- [x] 所有端点返回四字段信封（success/data/error/meta）
- [x] 示例与默认文案为中文；真实数据语言以运行时为准
- [x] 无任何指向生产 Runtime 的连接配置（适配层只读本进程 Runtime 状态）
- [x] UI 层只依赖协议与 Store，不 import Mock/Live 具体类型（双仓 grep 证实零残留）

## 4. 端到端证据

见 NEXARA-PRODUCT/evidence/integration-v1/：
- runtime-access-log.txt — 客户端对全部六个活跃端点的真实拉取记录
- live-missions-payload.json — 种子任务的契约负载
- live-system-status.json — 系统状态契约负载
- E2E_VERIFICATION.md — 验收链路说明

## 5. 已知限制（诚实声明）

1. `/v1/token/usage` 为确定性占位值（0/50000）：PRIME 暂无 token 计量，V1.3 接入。
2. `energyLevel` 为确定性推导（健康 0.85 / 降级 0.40）：无真实精力来源。
3. 截图证据未取得：本机 TCC 未授予屏幕录制权限。
4. `/v1/agents`、`/v1/evaluations` 保持预留（data: null），按契约 V1.3 定义。
5. 对话消息角色当前仅 user/assistant；出现新角色时会映射为 user（前瞻性风险已记录）。

## 6. 待人类决策

- 双仓推送（NSEC Article 37 要求人类批准；且本机 SSH 密钥当前被 GitHub 拒绝，
  需先解决 git@github.com:myorg/NEXARA-PRODUCT.git 的访问权限）。
