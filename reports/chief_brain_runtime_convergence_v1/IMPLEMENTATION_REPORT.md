# Chief Brain Runtime Convergence V1 — Implementation Report

## Audit Correction

原始任务书假设可能存在 Supervisor 类或多个平行编排器。**真实代码审计确认：
仓库中不存在 Supervisor 类。** 所有多 Agent 编排调用轨迹均指向
NexaraRuntime（runtime.py:199）作为事实中央编排器。

本轮未创建第二套 Chief Brain Runtime。采用强化现有 NexaraRuntime
入口、统一 API/CLI/UI、纠正 Provider 默认策略的方式完成收敛。

此调整属于 Reality First（NSEC 第二十八条），不属于 Scope Deviation。

## Scope

| 阶段 | 文件数 | 新增测试 | 说明 |
|------|--------|----------|------|
| V1 收敛 | 4 | 27 | NexaraRuntime 强化, inspect_mission, provider 策略 |
| PR #17 闭包 | 5 | 31 | 真实 Crash 恢复, Provider 不可用, 入口收敛 |
| **合计** | **9** | **58** | 800/800 PASS |

修改文件：
- `src/nexara_prime/runtime.py` — NexaraRuntime 唯一 Runtime Authority, UnavailableProvider
- `src/nexara_prime/model_gateway.py` — 新增 UnavailableProvider, 移除结构性 MockProvider 风险
- `tests/test_chief_brain_runtime_convergence.py` (27 新增)
- `tests/test_pr17_crash_recovery.py` (3 新增)
- `tests/test_pr17_provider_unavailable.py` (13 新增)
- `tests/test_pr17_entry_convergence.py` (15 新增)

## Runtime Authority

| 权威 | 路径 | 状态 |
|------|------|------|
| Mission 创建 | `NexaraRuntime.create_mission()` | CONVERGED |
| Mission 状态推进 | `NexaraRuntime._advance()` → `MissionStateMachine` | CONVERGED |
| Approval 暂停与恢复 | `NexaraRuntime.approve_mission()` / `resume()` | CONVERGED |
| Runtime Snapshot | `NexaraRuntime.inspect_mission()` | CONVERGED |
| Finalization | `NexaraRuntime._completion_gate()` | CONVERGED |
| Recovery | `DurableRecovery` + `resume()` crash path | CONVERGED |

## Provider Policy

- **UnavailableProvider** (新增): 每次调用立即抛出 ProviderUnavailable — 确保无 Provider 配置时不得静默进入 COMPLETED
- MockProvider: 仅显式 `mock_model=True`
- 生产: 显式配置 provider (openai_compatible, local)
- 无配置: 进入 `_provider_unavailable = True`, snapshot 显示 `provider: "unavailable"`

## Approval Resume E2E

E2E 完整闭环: create → plan → contract → approval → execute → verification → evidence → memory → evaluation → complete。
Resume 保持原 Mission ID；Pending Action 绑定不变。

## Crash Recovery (PR #17 — Runtime Truth OnePass Closure)

**三种真实场景均通过持久化 SQLite + 重新实例化 NexaraRuntime 验证:**

| 场景 | 测试 | 结果 |
|------|------|------|
| A — 执行前重启 | 新 Runtime 加载持久 DB → 恢复 → 完成 | PASS |
| B — 工具成功 / Evidence 提交前重启 | Evidence count 前后一致；0 重复副作用 | PASS |
| C — WAITING_APPROVAL 后重启 | mission_id + pending_action_id 不变；批准后继续 | PASS |

所有场景均跨 Runtime 重新实例化（`del rt1; rt2 = NexaraRuntime()`），非简单 pause/resume。

## API CLI UI Convergence (PR #17)

| 入口 | 验证方式 | 结果 |
|------|----------|------|
| API | TestClient → `/api/missions` → runtime.list_missions 核对 | PASS |
| CLI | argparse parser → main() → NexaraRuntime | PASS |
| UI backend | `/api/runtime/overview` → runtime.overview() | PASS |
| Scheduler 唯一入口 | AST 审计 — AdaptiveScheduler() 仅 runtime.py 调用 | PASS |
| 无入口自推进状态 | AST 审计 — `_advance()` 仅 runtime.py 调用；`api.py` 无 `.state` 直接赋值 | PASS |

## Compatibility

所有旧 API 路径保持不变 — 无公开接口破坏。新增 `inspect_mission()` 为追加方法。

## Verification

| Check | Result |
|-------|--------|
| Full test suite | **800/800 PASS** (742 baseline + 58 new) |
| NSEC Validator | PASS |
| Drift Detector | NO DRIFT |
| Ruff (new code) | CLEAN (0 unused imports) |
| Ruff (total) | PASS_WITH_PRE_EXISTING_E501_BASELINE |
| Secret scan | CLEAN |
| Import cycles | NONE |
| Provider unavailable | PASS (UnavailableProvider blocks completion) |

## Known Limitations

- Provider unavailable 标记后不自动重试 — 需人工重新配置 Provider
- 真实进程崩溃测试依赖持久化 SQLite — 信号/电源故障级测试需集成测试环境

## Final Decision

**PASS.** NexaraRuntime 已确认并强化为唯一 Chief Brain Runtime Authority。
PR #17 Runtime Truth OnePass Closure 修复了 Provider 不可用路径的结构性漏洞，
补充了三种真实进程重启崩溃恢复场景，并完成了 API/CLI/UI 入口收敛验证。

## Document Consolidation Decision

| 原定文档 | 实际文件 | 对应章节 |
|----------|----------|----------|
| AUTHORITY_MATRIX.yaml | AUTHORITY_MATRIX.yaml (独立) | 完整矩阵 |
| RECEIPT | RECEIPT_*.json (独立) | 可验证接收单 |
| 其余 14 份原定文档 | IMPLEMENTATION_REPORT.md (合并) | 对应章节 |
