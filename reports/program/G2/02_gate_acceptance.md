# G2 — Gate Acceptance

**Gate:** G2 — Mission Agent 闭环
**Verdict:** PASS
**Date:** 2026-07-15
**Effort:** 150 units (verified — loop pre-exists, gate is verification + documentation)

## Exit Criteria

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Intent → Context → Contract → Plan flow | ✅ PASS (plan_mission) |
| 2 | Execute → Verify → Evidence flow | ✅ PASS (run_mission) |
| 3 | Evidence → Memory promotion | ✅ PASS (memory.py + evidence.py) |
| 4 | Memory → Evaluation → Complete | ✅ PASS (evaluation.py) |
| 5 | Full lifecycle E2E tests | ✅ 14 tests passing |
| 6 | State machine with proper transitions | ✅ 28 states, guarded |
| 7 | Evidence hash integrity | ✅ Verified |
| 8 | Rollback path | ✅ Available at all stages |
| 9 | Blocked/Failed handling | ✅ Escape paths at every state |
| 10 | 508/508 full regression | ✅ PASS |

## Key Modules

| Module | Purpose | Lines |
|--------|---------|-------|
| `runtime.py` | Mission lifecycle orchestration | ~400 |
| `state_machine.py` | State transition guards | ~50 |
| `mission_compiler.py` | Intent → MissionSpec | ~50 |
| `contract_engine.py` | Mission → WorkContract | ~50 |
| `adaptive_scheduler.py` | Plan generation + assignments | ~300 |
| `evidence.py` | Evidence envelope + hash chain | ~100 |
| `memory.py` | Evidence-backed memory store | ~100 |
| `evaluation.py` | Quality scoring + evolution | ~100 |

## Next Gate: G3

**G3 — Platform Runtime Services**
- Depends on: G2 ✅
- Exit condition: Capability/Policy/Telemetry/Knowledge 服务从 YAML 变成可运行服务
- Effort: 150 units
