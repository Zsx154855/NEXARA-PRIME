# G2 — Mission Agent 闭环

**Gate:** G2 — Mission Agent 闭环
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: Intent→Context→Contract→Plan→Execute→Verify→Evidence→Memory 全闭环

### End-to-End Flow (Verified)

```
INTENT (mission_compiler.py)
  → CONTEXT (runtime.py: plan_mission, context snapshot)
  → CONTRACT (contract_engine.py: WorkContract generation)
  → PLAN (adaptive_scheduler.py: Task DAG + assignments)
  → SIMULATION (runtime.py: risk/cost simulation)
  → APPROVAL (runtime.py: R0-R4 gating)
  → EXECUTION (runtime.py: run_mission, tool invocation, sandbox)
  → VERIFICATION (runtime.py: test/assert/acceptance checks)
  → EVIDENCE (evidence.py: EvidenceEnvelope, hash, receipt)
  → MEMORY_PATCH (memory.py: evidence-backed memory promotion)
  → EVALUATION (evaluation.py: quality scoring)
  → COMPLETED (runtime.py: final state)
```

### State Machine (`state_machine.py`)

28 distinct mission states with proper transition guards:
- INTENT → CONTEXT → CONTRACT → PLAN → SIMULATION → APPROVAL/EXECUTION
- EXECUTION → VERIFICATION → EVIDENCE → MEMORY_PATCH → EVALUATION → COMPLETED
- Blocked/Failed/RolledBack escape paths at every stage

### E2E Test Results

| Test | Coverage | Status |
|------|----------|--------|
| test_full_acceptance_flow | Complete lifecycle | ✅ PASS |
| test_e2e_report_mission | Report generation | ✅ PASS |
| test_e2e_evidence_mission | Evidence collection | ✅ PASS |
| test_e2e_memory_mission | Memory patching | ✅ PASS |
| test_e2e_evaluation_mission | Evaluation scoring | ✅ PASS |
| test_e2e_report_hash_is_present | Hash integrity | ✅ PASS |
| test_matrix_e2e_00-02 | Matrix scenarios | ✅ PASS |

**Total: 14 E2E tests, all passing.**

### Actor Model

| Phase | Actor |
|-------|-------|
| Plan (context→plan) | nexara |
| Approval | governance |
| Execution | policy / nexara |
| Verify + Evidence | reviewer |
| Memory | archivist |
| Evaluation | kairos |
| Rollback | human |

The first-party agent (nexara) owns plan→execution transitions. Governance, verification, and evaluation are separated concerns.
