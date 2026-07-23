# 03 — Authority/Duplication Report

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

---

## 3.1 Authority Hierarchy (per governance/authority_index.yaml)

```
Tier 0: Reality Override (verified reproducible facts)
Tier 1: Human Explicit Directive (current unambiguous human instruction)
Tier 2: NSEC V2.1 (Sovereign Engineering Constitution)
Tier 3: Program Constitution (NEXARA_PROGRAM_CONSTITUTION_V1.md)
Tier 4: Governance Contracts (merge/release/rollback)
Tier 5: Program State (.nexara/GATE_STATUS.json, PROGRAM_STATE.json)
Tier 6: Evidence (.nexara/evidence/*, reports)
Tier 7: Implementation (source code + tests)
Tier 8: Model Judgment (AI outputs — lowest)
```

## 3.2 Authority Conflicts Detected

### CONFLICT-001: GATE_STATUS.json vs Forensic Audit (CRITICAL)

| Source | G7 | G8 | G9 | G10 |
|--------|----|----|----|-----|
| `.nexara/GATE_STATUS.json` | PASS | PASS | PASS | (composite) |
| `reports/.../forensic_audit/09_corrected_gate_status.json` | PARTIAL | NOT_STARTED | PARTIAL | BLOCKED |

**Resolution:** Forensic Audit is Tier 6 Evidence, GATE_STATUS.json is Tier 5 Program State. Forensic Audit was produced later with explicit verification methodology. **Forensic Audit prevails per Reality Override (Tier 0).** GATE_STATUS.json is stale/false.

### CONFLICT-002: PROJECT_FACTS.json vs PROGRAM_STATE.json test count (LOW)

| Source | Test Count |
|--------|-----------|
| `PROJECT_FACTS.json` | 507 passed |
| `PROGRAM_STATE.json` | 682 passed |
| Current HEAD actual | 682 passed |

**Resolution:** PROJECT_FACTS.json is stale (frozen at earlier baseline). PROGRAM_STATE.json is authoritative.

### CONFLICT-003: NSEC V1 vs NSEC V2.1 (RESOLVED)

- `governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md` — SUPERSEDED
- `governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md` — AUTHORITATIVE (19章55条)

**Resolution:** V2.1 explicitly supersedes V1. V1 retained for audit trail only.

### CONFLICT-004: CLAUDE.md vs AGENTS.md tech stack

| Source | Python Version |
|--------|---------------|
| `CLAUDE.md` | Python 3.9 |
| `AGENTS.md` | Python 3.12 |
| `pyproject.toml` | >=3.12 |
| `.venv` actual | 3.12.13 |

**Resolution:** CLAUDE.md is stale. Reality (Tier 0): Python 3.12.13.

---

## 3.3 Duplication Analysis

### DUPLICATE-001: capability_registry_v2.py (RESOLVED)

- `capability_registry_v2.py` — explicitly marked DEPRECATED, re-exports from `capabilities.py`
- **Verdict:** Intentional backward-compat alias, to be removed in v0.2.0

### DUPLICATE-002: token_compiler.py + token_compiler_v2.py (ACTIVE)

- Both files exist side by side
- `token_compiler_v2.py` likely supersedes `token_compiler.py`
- No deprecation marker on `token_compiler.py`
- **Risk:** Duplicate maintenance burden, import ambiguity
- **Recommendation:** Mark `token_compiler.py` as deprecated, converge to V2

### DUPLICATE-003: orchestration.py vs program_loop.py (OVERLAP)

- `orchestration.py` — persistent control plane (MissionQueue, WorkerScheduler, WriterLease, etc.)
- `program_loop.py` — continuous background loop (Load→Select→Acquire→Execute→Verify→Persist→Checkpoint)
- Both manage mission execution lifecycle
- **Risk:** Two competing execution loops with overlapping responsibility
- **Recommendation:** Clarify orchestration.py as the authoritative execution plane; program_loop.py as the daemon wrapper

### DUPLICATE-004: governance.py PolicyEngine vs aos/policy_engine.pyc (SOURCE MISSING)

- `governance.py` has PolicyEngine with R0-R4 rules
- `aos/policy_engine.pyc` (5.2K) — compiled bytecode, source MISSING
- **Risk:** Two policy engines may diverge; AOS version unrecoverable
- **Verdict:** governance.py is authoritative (source available). AOS policy_engine functionally lost.

### DUPLICATE-005: scheduler.py vs adaptive_scheduler.py vs aos/worker_adapters.pyc (OVERLAP)

- `scheduler.py` — AdaptiveScheduler (persona-based role assignment)
- `adaptive_scheduler.py` — AdaptiveMultiAgentScheduler (ROI-gated dynamic allocation)
- `aos/worker_adapters.pyc` — compiled worker adapter, source MISSING
- **Risk:** Three scheduling mechanisms; which is authoritative?
- **Recommendation:** adaptive_scheduler.py as authoritative; deprecate scheduler.py; AOS worker_adapters lost

### DUPLICATE-006: UI types/index.ts vs Python models.py (EXPECTED)

- TypeScript type definitions mirror Python Pydantic models
- This is expected cross-platform duplication — acceptable
- **Risk:** Type drift between Python and TypeScript definitions
- **Recommendation:** Generate TypeScript types from Python models (or OpenAPI) at build time

### DUPLICATE-007: ui/app.js vs ui/src/ (LEGACY)

- `ui/app.js` — vanilla JS dashboard (pre-Next.js)
- `ui/src/` — Next.js 16 React dashboard
- **Verdict:** app.js is legacy, retained for reference. Should be archived to docs/99-Legacy/

---

## 3.4 Single Writer Authority Map

Per Blueprint §4.6 and NSEC V2.1 Article 36:

| Domain | Single Writer | Current State |
|--------|--------------|---------------|
| Source code | `src/nexara_prime/` files | ✅ One git repo, one main branch |
| Program State | `.nexara/PROGRAM_STATE.json` | ✅ Single file |
| Gate Status | `.nexara/GATE_STATUS.json` | ⚠️ CONFLICT with forensic audit |
| Evidence | `.nexara/evidence/*` | ✅ Append-only |
| Runtime DB | `runtime/nexara.db` | ✅ SQLite WAL |
| Documentation | `docs/` | ✅ Git-tracked |
| Governance | `governance/` | ✅ NSEC V2.1 authoritative |
| Build Artifacts | `dist/` | ✅ Versioned |
| UI | `ui/src/` | ✅ Next.js single app |

---

## 3.5 Authority Gap: AOS Source Files

**13 AOS modules exist only as `.pyc` bytecode:**

```
aos/__pycache__/
  supervisor.cpython-312.pyc          (58.6K)
  command_classifier.cpython-312.pyc  (46.4K)
  worker_adapters.cpython-312.pyc     (23.4K)
  execution_gateway.cpython-312.pyc   (12.4K)
  permission_broker.cpython-312.pyc   (9.3K)
  runtime_truth_adapter.cpython-312.pyc (8.4K)
  cost_optimizer.cpython-312.pyc      (8.5K)
  recovery_engine.cpython-312.pyc     (6.4K)
  health_monitor.cpython-312.pyc      (5.6K)
  notification_gateway.cpython-312.pyc (5.3K)
  policy_engine.cpython-312.pyc       (5.2K)
  loop_tool_adapter.cpython-312.pyc   (4.3K)
  context_compactor.cpython-312.pyc   (3.7K)
```

**This is a CRITICAL authority gap:**
- No `.py` source in git history at current HEAD
- Cannot be rebuilt, audited, or modified
- Violates NSEC V2.1 第34条 (Single Source of Truth — code must be in source form)
- Represents ~200KB of compiled logic with zero auditability
- **Action:** Either recover source files from another branch/worktree or declare AOS as lost and plan reconstruction

---

## 3.6 Authority Summary

| Status | Count | Items |
|--------|-------|-------|
| ✅ Authoritative | 42 | All source modules, NSEC V2.1, tests, docs, governance |
| ⚠️ Conflict | 2 | GATE_STATUS.json (stale), CLAUDE.md (stale Python version) |
| 🔴 Duplicated | 4 | token_compiler (V1+V2), orchestration+program_loop, scheduler×3, legacy UI |
| 💀 Authority Gap | 1 | 13 AOS modules — source MISSING |
| 📋 Expected Duplication | 1 | TypeScript types ↔ Python models |
