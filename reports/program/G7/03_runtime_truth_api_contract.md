# Runtime Truth API Contract — G7 Frozen

**Version:** 1.0
**Frozen:** 2026-07-15
**Authority:** NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md §18

## Mission States (visible to UI)

| State | 中文 | UI Behavior |
|-------|------|------------|
| DRAFT | 草稿 | Composer only |
| CONTEXT_READY | 上下文就绪 | Context panel populated |
| CONTRACTED | 已签约 | Contract view active |
| PLANNED | 已规划 | Plan view with Task DAG |
| SIMULATED | 已模拟 | Simulation results shown |
| APPROVAL_REQUIRED | 待审批 | Approval gate active |
| READY | 就绪 | Execute button enabled |
| RUNNING | 执行中 | Live runtime stream |
| VERIFYING | 验证中 | Test/assert progress |
| COMPLETED | 已完成 | Evidence + receipt |
| PAUSED | 已暂停 | Resume available |
| BLOCKED | 已阻断 | Blocker details shown |
| FAILED | 已失败 | Failure analysis |
| ROLLING_BACK | 回滚中 | Recovery progress |
| ROLLED_BACK | 已回滚 | Safe state confirmed |
| CANCELLED | 已取消 | Termination receipt |

## Execution Modes

| Mode | Display | API Flag | UI Indicator |
|------|---------|----------|-------------|
| Mock | 模拟 | `mock_model: true` | 橙色虚线边框 |
| Dry Run | 预演 | `mock_model: false, safe_mode: true` | 蓝色虚线边框 |
| Local | 本地 | `mock_model: false, live: false` | 绿色实线边框 |
| Live | 外部执行 | `live: true, external` | 红色实线+警告 |

## API Endpoints (Runtime Truth Surface)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Connection health + provider info |
| GET | `/api/runtime/overview` | System state summary |
| GET | `/api/missions` | List all missions |
| POST | `/api/missions` | Create mission |
| GET | `/api/missions/{id}` | Mission detail |
| POST | `/api/missions/{id}/plan` | Generate plan |
| POST | `/api/missions/{id}/approve` | Human approval |
| POST | `/api/missions/{id}/run` | Execute mission |
| POST | `/api/missions/{id}/pause` | Pause mission |

## Rule: No Mock/Live Confusion

UI must never display "live" when running in mock mode. The `overview.system.mock_default` flag is authoritative. UI state labels MUST derive from API response, never from hardcoded assumptions.
