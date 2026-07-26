# G2-A Kernel Boundary Mapping — Evidence

**Date:** 2026-07-24
**Gate:** G2-A (Kernel Boundary Mapping)
**Status:** COMPLETE
**Evidence Head:** `6ab0630`

---

## Analysis Summary

Three independent analysis streams converged on the same boundary:

### Kernel IS (7 modules, already implemented)

| Module | Lines | Role |
|--------|-------|------|
| `runtime.py` | 1,083 | Composition root — NexaraRuntime |
| `orchestration.py` | 935 | 7-subsystem autonomous orchestrator |
| `state_machine.py` | 115 | 29-state transition engine |
| `mission_triage.py` | 350 | Intent classification + risk scoring |
| `mission_compiler.py` | 65 | Spec→Plan translation |
| `contract_engine.py` | 24 | WorkContract lifecycle |
| `adaptive_scheduler.py` | 480 | Multi-agent capability-based scheduling |

### Kernel DEPENDS ON (infrastructure, not kernel)

| Module | Relationship |
|--------|-------------|
| `db.py` (SQLiteStore) | DEPENDS_ON — persistence |
| `api.py` (FastAPI) | EXPOSED_BY — REST interface |
| `cli.py` | EXPOSED_BY — CLI interface |
| `model_gateway.py` | DEPENDS_ON — LLM abstraction |
| `model_router.py` | DEPENDS_ON — model selection |
| `tools.py` (ToolRuntime) | DEPENDS_ON — sandbox execution |
| `capabilities.py` | DEPENDS_ON — capability registry |
| `evidence.py` (EvidenceStore) | DEPENDS_ON — independent evidence domain |
| `memory.py` (MemoryKernel) | DEPENDS_ON — independent memory domain |
| `evaluation.py` | DEPENDS_ON — independent audit |
| `governance.py` | GOVERNED_BY — kernel obeys governance |

### Kernel is GOVERNED BY

- **NSEC V2.1** — supreme engineering constitution
- **G1 Contracts** — frozen domain model, authority matrix, 5 invariants
- **Authority Matrix** — 15-object create/modify/read rules
- **5 Invariants** — Skill/Permission, Canvas/Runtime, Executor/Verdict, Memory/Evidence, Mission/Complete Chain

---

## Contract Output

**File:** `.nexara/contracts/chief_brain_kernel_contract_v1.yaml`

Contains:
1. Kernel responsibility boundary (7 IN SCOPE, 12 OUT OF SCOPE)
2. Input/Output contract (5 inputs, 5 outputs, 3 error states)
3. Existing body mapping (5 relationship categories)
4. 7 prohibited behaviors (mapped to 5 invariants)
5. G2 implementation dependency graph (G2-A → G2-B → G2-C → G2-D → G2 Closure)

---

## Key Finding

**No new code needed for kernel.** The kernel already exists as `NexaraRuntime` + `RuntimeOrchestrator` + `MissionStateMachine` + supporting engines. G2 formalizes this by adding an explicit `ChiefBrainKernel` boundary wrapper — thin, non-invasive, purely contractual.

---

## Validation

```yaml
nsrc: PASS
program_state: overall_pass=true
tests: 945 passed, 0 failed
contract_yaml: VALID
analysis_streams: 3 independent agents converged
```
