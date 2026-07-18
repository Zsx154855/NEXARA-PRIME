# Truth / State Authority Convergence Report

## Pre-Convergence State

Three authoritative files in `.nexara/`:

| File | Semantic Domain | Writer |
|------|----------------|--------|
| `.nexara/PROGRAM_STATE.json` | Project identity + metrics | `scripts/runtime_truth/compile_program_state.py` |
| `.nexara/GATE_STATUS.json` | Gate progression (G0-G10) | Manual + CI gates |
| `.nexara/BASELINE.json` | Historical frozen baseline | One-time freeze (2026-07-14) |

Plus legacy/deprecated files:

| File | Status |
|------|--------|
| `.nexara/PROJECT_STATE.json` | DEPRECATED — superseded by PROGRAM_STATE.json |
| `.nexara/CURRENT_GATE.md` | DEPRECATED — migrated to GATE_STATUS.json |
| `.nexara/NEXT_ACTION.md` | DEPRECATED — migrated to PROGRAM_STATE.json |
| `.nexara/EXECUTION_CHECKPOINT.json` | DEPRECATED — migrated to GATE_STATUS.json |

## Convergence Decision

**No structural change.** Three active files serve three different, non-overlapping semantic domains. Single authoritative writer per domain:

| Domain | Writer | No Conflict With |
|--------|--------|-----------------|
| Project identity | `compile_program_state.py` → PROGRAM_STATE.json | GATE_STATUS, BASELINE |
| Gate progression | Manual + CI → GATE_STATUS.json | PROGRAM_STATE, BASELINE |
| Historical baseline | One-time freeze → BASELINE.json (IMMUTABLE) | PROGRAM_STATE, GATE_STATUS |

**Conflict resolution rule**: When two files claim the same semantic domain, the higher-tier writer wins.

**Verification**: `scripts/governance/detect_state_drift.py` validates PROGRAM_STATE and GATE_STATUS agree when they should.

## Verification

| Check | Result |
|-------|--------|
| Authoritative writers per domain | 1 per domain |
| No overlapping domains | Confirmed |
| Legacy files documented | Yes |
| Drift detection script | `scripts/governance/detect_state_drift.py` |
| NSEC compliance | Article IX (Single Truth) — satisfied |
