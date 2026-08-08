# NEXARA Core v1.0 — Architecture Audit

**Generated**: 2026-08-08T08:00:00Z | **HEAD**: `8a75910`

---

## Classification Legend

| Class | Meaning |
|---|---|
| **KEEP** | Single responsibility, clean, no issues — freeze as-is |
| **MERGE** | Duplicate responsibility — consolidate into single owner |
| **SPLIT** | Too many responsibilities in one module |
| **DELETE** | Dead code, thin wrappers, deprecated |
| **DEPRECATED** | Still used but planned for removal |
| **UNKNOWN** | Needs deeper investigation |

---

## Core Kernel Modules

| Module | File | Classification | Evidence | Reason | Risk | Migration Impact |
|---|---|---|---|---|---|---|
| **Runtime** | `runtime.py` (1105L) | **KEEP** | Composes all 19 kernel services; 5-stage pipeline verified by 2044 tests; 10 runtime invariants documented | Single composition root, well-structured | LOW — large file but cohesive | None — freeze as-is |
| **Models** | `models.py` (909L) | **KEEP** | ALL canonical types in one file; 33 enums + 40+ Pydantic models; single source of truth per NSEC Art.30 | Single authority for all data types | LOW — large but canonical | None — freeze as-is |
| **State Machine** | `state_machine.py` (71L) | **KEEP** | `TRANSITIONS` matrix covers 33 states; clean, minimal, testable | Single authority for state transitions | LOW | None — freeze as-is |
| **Governance** | `governance.py` (500L) | **KEEP** | PolicyEngine + ApprovalEngine + WriterLeaseManager in one file; integrity-validated transitions | Cohesive governance triad | LOW | None — freeze as-is |
| **DB** | `db.py` (1294L) | **KEEP** | SQLiteStore — single persistence authority; envelope integrity; event sourcing | Only one canonical DB | MEDIUM — large file | None — freeze as-is |
| **Events** | `events.py` | **KEEP** | EventBus — publish/subscribe; clean separation from store | Single event authority | LOW | None — freeze as-is |
| **Evidence** | `evidence.py` | **KEEP** | EvidenceStore — SHA-256, envelope integrity, idempotency, receipt tracking | Single evidence authority | LOW | None — freeze as-is |
| **Memory** | `memory.py` | **KEEP** | MemoryKernel + MemoryLayerManager — evidence-bound patches | Single memory authority | LOW | None — freeze as-is |
| **Evaluation** | `evaluation.py` | **KEEP** | EvaluationEngine — 6-dim idempotent evaluation | Single evaluation authority (top-level) | LOW | None — freeze as-is |
| **Tools** | `tools.py` | **KEEP** | ToolRuntime — governed tool invocation with policy check | Single tool authority | LOW | None — freeze as-is |
| **Capabilities** | `capabilities.py` (491L) | **KEEP** | CapabilityRegistry — single authority | Single capability authority (top-level) | LOW | None — freeze as-is |
| **Recovery** | `recovery.py` | **KEEP** | DurableRecovery — checkpoint/idempotency | Single recovery authority | LOW | None — freeze as-is |
| **CLI** | `cli.py` (615L) | **KEEP** | Mission CLI — create/status/plan/approve/run | Primary human interface | LOW | None — freeze as-is |
| **API** | `api.py` (235L) | **KEEP** | FastAPI REST — inspect_mission, SDK compatibility | Primary machine interface | LOW | None — freeze as-is |
| **Config** | `config.py` (38L) | **KEEP** | Settings — from_env, model_provider, mock_model | Single config authority | LOW | None — freeze as-is |
| **Soul** | `soul.py` | **KEEP** | SoulKernel — constitutional identity | Exported in `__init__.py` | LOW | None — freeze as-is |

---

## Duplicates — MERGE Required

| Module | File | Classification | Evidence | Reason | Risk | Migration Impact |
|---|---|---|---|---|---|---|
| **Brain DB** | `brain/db.py` (249L) | **MERGE → db.py** | Duplicates top-level `db.py` (1294L); both have SQLite store semantics | Two DB layers = two truth sources (NSEC Art.30 violation) | **HIGH** — data inconsistency | Merge brain/db.py functionality into top-level db.py; update brain imports |
| **Brain CBK** | `chief_brain_kernel.py` (294L) | **MERGE → brain/kernel.py** | Top-level `chief_brain_kernel.py` delegates to `brain/kernel.py`; two ChiefBrainKernel classes | Conflicting Mission Admission Boundaries | **HIGH** — divergent behavior | Consolidate into `brain/kernel.py`; remove top-level file |
| **Brain Compiler** | `brain/mission_compiler.py` (285L) | **MERGE → mission_compiler.py** | Two mission compilers with overlapping semantics | Divergent compilation | MEDIUM | Merge brain version into top-level; remove brain copy |
| **Brain Capability** | `brain/capability_registry.py` (247L) | **MERGE → capabilities.py** | Two capability registries | Divergent capability state | MEDIUM | Merge brain version into top-level (491L); remove brain copy |
| **Brain Eval** | `brain/evaluation_engine.py` (147L) | **MERGE → evaluation.py** | Two evaluation engines | Divergent evaluation criteria | MEDIUM | Merge brain version into top-level; remove brain copy |

---

## Deprecated / DELETE

| Module | File | Classification | Evidence | Reason | Risk | Migration Impact |
|---|---|---|---|---|---|---|
| **Cap V2** | `capability_registry_v2.py` (10L) | **DELETE** | 10-line thin wrapper around capabilities.py | Dead code — no unique functionality | LOW | Remove file; update any imports |
| **CURRENT_GATE.md** | `.nexara/CURRENT_GATE.md` | **DELETE** | Marked DEPRECATED, content migrated to GATE_STATUS.json | Legacy file — no longer authoritative | LOW | Physical removal in cleanup |
| **NEXT_ACTION.md** | `.nexara/NEXT_ACTION.md` | **DELETE** | Marked DEPRECATED, content migrated to PROGRAM_STATE.json | Legacy file — no longer authoritative | LOW | Physical removal in cleanup |
| **EXECUTION_CHECKPOINT** | `.nexara/EXECUTION_CHECKPOINT.json` | **DELETE** | Marked DEPRECATED, content migrated to GATE_STATUS.json | Legacy file — preserved for audit trail only | LOW | Physical removal in cleanup |

---

## SPLIT Candidates

| Module | File | Classification | Evidence | Reason | Risk | Migration Impact |
|---|---|---|---|---|---|---|
| **Brain Init** | `brain/__init__.py` (133L) | **SPLIT** | 133-line init is anti-pattern; should be thin re-exports | Opaque initialization logic | LOW | Extract init logic into explicit module; thin __init__.py |

---

## KEEP — Active Subpackages

| Package | Classification | Reason |
|---|---|---|
| `council/` (16 files) | **KEEP** | Multi-provider adapter system; pipeline execution; mission routing |
| `connectors/` (9 files) | **KEEP** | Governed external connectors (browser, HTTP, audit) |
| `secrets/` (5 files) | **KEEP** | Multi-backend secret storage (env, keychain, memory) |
| `product_reality/` (4 files) | **KEEP** | Product genome, digital twin, evolution |
| `delivery_controller/` (2 files) | **KEEP** | Delivery migration control |
| `brain/` (remaining ~30 files) | **KEEP** | Reasoning, memory, evolution, planning, cognition — unique functionality not duplicated at top level |

---

## UNKNOWN

| Module | File | Reason |
|---|---|---|
| `agent/` (1 file) | `agent/__init__.py` | Thin package — role unclear, may be placeholder |
| `platform/` (1 file) | `platform/__init__.py` | Thin package — role unclear, may be placeholder |

---

## Architecture Audit Summary

| Classification | Count |
|---|---|
| **KEEP** | 16 core modules + 5 subpackages |
| **MERGE** | 5 duplicate pairs (brain/* → top-level) |
| **SPLIT** | 1 (brain/__init__.py) |
| **DELETE** | 4 (1 dead code + 3 deprecated .nexara files) |
| **DEPRECATED** | 0 (all deprecated items recommended for DELETE) |
| **UNKNOWN** | 2 (agent/, platform/ placeholders) |

### Freeze Blocking Issues

| # | Issue | Blocks Freeze? |
|---|---|---|
| A1 | D1: Two DB layers | **YES** — single source of truth violation |
| A2 | D2: Two ChiefBrainKernels | **YES** — conflicting Mission Admission Boundaries |
| A3 | D3-D5: Other duplicates | **NO** — can freeze with note, resolve post-freeze |

---

**End of Architecture Audit**
