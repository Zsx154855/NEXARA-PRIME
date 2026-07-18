# NEXARA Product Convergence V1 — Compatibility & Deprecation Plan

## Changed Modules

| Old | New | Migration Window | Removal Target |
|-----|-----|-----------------|----------------|
| `capability_registry_v2.CapabilityRegistryV2` | `capabilities.CapabilityRegistry` | v0.1.x (current) | v0.2.0 |
| `token_compiler_v2.TokenCompilerV2` | `token_compiler.TokenCompiler` | v0.1.x (current) | v0.2.0 |

## Backwards Compatibility

Both old modules still import and work:
- `from nexara_prime.capability_registry_v2 import CapabilityRegistryV2` → redirected to `capabilities.CapabilityRegistry`
- `from nexara_prime.token_compiler_v2 import TokenCompilerV2` → redirected to `token_compiler.TokenCompiler`

No caller changes required. Deprecation warning not emitted (non-breaking compat period).

## Scheduler

No change. `scheduler.AdaptiveScheduler` remains the single authoritative scheduler entry.
5 orchestration modules are internal components accessed through the scheduler/runtime layer only.

## Truth/State

No code change. Authority Matrix at `reports/product_convergence_v1/AUTHORITY_MATRIX.yaml`.
3 authoritative files preserved — no semantic conflict between PROGRAM_STATE, GATE_STATUS, BASELINE.

## Deprecated Files (audit-trail only)
- `.nexara/CURRENT_GATE.md` — content migrated to GATE_STATUS.json
- `.nexara/NEXT_ACTION.md` — content migrated to PROGRAM_STATE.json
- `.nexara/EXECUTION_CHECKPOINT.json` — content migrated to GATE_STATUS.json
- `.nexara/PROJECT_STATE.json` — superseded by PROGRAM_STATE.json
