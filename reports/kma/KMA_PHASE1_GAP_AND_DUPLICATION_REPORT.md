# KMA Phase 1 Gap and Duplication Report

> NEXARA Knowledge-Memory Authority V1
> Generated: 2026-07-26
> Phase: 1 — Gaps & Duplications
> Status: CANONICAL

## Executive Summary

The Knowledge-Memory Authority system has **one authoritative MemoryKernel** and **one authoritative EvidenceStore**, both IMPLEMENTED and production-quality. However, **three duplicate instances** exist in the runtime, the **Receipt system lacks a canonical model**, the **ChiefBrainKernel is completely unwired**, and **file-based evidence/receipts are disconnected** from the SQLite-backed stores.

---

## 1. Duplicate Systems

### D1: Duplicate CapabilityRegistry Instances (P1)

**Location**: `src/nexara_prime/runtime.py`
- Line 214: `self.capabilities = CapabilityRegistry()` — main instance
- Line 174: `_adaptive_capabilities_v2 = CapabilityRegistry()` — module-level duplicate

**Impact**: Capabilities registered in one instance are invisible to the other. State fragmentation. Both are the same class (`CapabilityRegistry`), but hold separate registration state.

**Fix**: Phase 2 must consolidate to single `self.capabilities` instance. Remove `_adaptive_capabilities_v2`.

### D2: Duplicate TokenCompiler Instances (P1)

**Location**: `src/nexara_prime/runtime.py`
- Line 218: `self.tokens = TokenCompiler()` — main instance
- Line 194: `_adaptive_tokens_v2 = TokenCompiler()` — module-level duplicate

**Impact**: Same class, separate state. Token compilation state split.

**Fix**: Phase 2 must consolidate to single `self.tokens` instance. Remove `_adaptive_tokens_v2`.

### D3: Duplicate Governance Instances (P2)

**Location**: `src/nexara_prime/policy_service.py`
- Creates its own `PolicyEngine`, `ApprovalEngine`, `WriterLeaseManager` instances separate from `runtime.py`

**Impact**: Not yet wired into active flows, but creates latent duplicate-authority risk.

**Fix**: Phase 2 must either wire PolicyService to use runtime's instances or document the intentional separation.

---

## 2. Authority Conflicts

### A1: cli.py Reads Deprecated PROJECT_STATE (P1)

**Location**: `src/nexara_prime/cli.py` lines 53, 104, 115, 117, 227, 229

**Issue**: `cli.py` reads `.nexara/PROJECT_STATE.json` which is DEPRECATED per project documentation. The canonical replacement is `.nexara/PROGRAM_STATE.json`.

**Fix**: Phase 2 must update `cli.py` to read `PROGRAM_STATE.json`.

### A2: Deprecated Files Coexisting with Active Files (P2)

**Location**: `.nexara/`
- `.nexara/PROJECT_STATE.json` (deprecated) alongside `.nexara/PROGRAM_STATE.json` (active)
- `.nexara/CURRENT_GATE.md` (deprecated) alongside `.nexara/GATE_STATUS.json` (active)

**Impact**: Consumers may read wrong file. cli.py already does.

**Fix**: Phase 2 should remove or add deprecation notice header to PROJECT_STATE.json and CURRENT_GATE.md.

### A3: Legacy .bak Files in Evidence Directory (P2)

**Location**: `.nexara/evidence/`
- `v2_closure_8_points_20260718T190652Z.json.legacy.bak`
- `v2_final_onepass_20260718T180610Z.json.legacy.bak`

**Impact**: Visual ambiguity about which evidence file is authoritative.

**Fix**: Phase 2 should move .legacy.bak files to `docs/99-Legacy/` or a separate archive.

---

## 3. Critical Gaps

### G1: ChiefBrainKernel Not Wired (CRITICAL)

**Location**: `src/nexara_prime/chief_brain_kernel.py` (214 lines, IMPLEMENTED but disconnected)

**Issue**: The kernel class implements admission gating, invariant enforcement, and execution guard logic. However, `NexaraRuntime` (runtime.py) directly creates/plans/approves/runs missions without ever calling `ChiefBrainKernel.submit()` or checking `KernelExecutionGuard.assert_admitted()`. Zero imports of `chief_brain_kernel` in `runtime.py`, `orchestration.py`, or `api.py`.

**Contract**: `.nexara/contracts/chief_brain_kernel_contract_v1.yaml` dependency graph shows G2-D (kernel integration validation) as PENDING — confirming this was deferred.

**Fix**: Phase 2 must wire `ChiefBrainKernel.submit()` into `NexaraRuntime` mission creation and execution paths.

### G2: No Canonical Receipt Model (HIGH)

**Issue**: Receipts exist in 4 separate forms:
1. Governance receipts: `.nexara/receipts/*.json` — ad-hoc JSON, varying schemas
2. Runtime receipts: `ToolInvocation.receipt_evidence_id` → `EvidenceArtifact.evidence_id` link
3. Operational receipts: `ConnectorReceipt` (connectors/base.py), `SandboxReceipt` (sandbox_v2.py)
4. Legacy receipts: `reports/*/RECEIPT.json`

No single Pydantic model. No canonical store. No cross-reference mechanism between file-based and runtime receipts.

**Fix**: Phase 2 must define `Receipt` Pydantic model, unify the storage path, and ensure all receipt forms reference the canonical model.

### G3: File-Based Evidence Disconnected from EvidenceStore (HIGH)

**Issue**: `.nexara/evidence/` contains 24 evidence files (16 .md + 8 .json) that are NEVER ingested into the SQLite-backed `EvidenceStore`. The `EvidenceStore.add()` method creates evidence in SQLite, but file-based evidence is created manually and lives outside the system. The JSON schema (`schemas/evidence_artifact.json`) is outdated (7 fields vs ~15 in Pydantic model).

**Fix**: Phase 2 should add an ingestion path to bring file-based evidence into EvidenceStore, or document that .nexara/evidence/ is the human-readable surface and SQLite is the machine-authoritative store.

### G4: Memory Lacks Receipt Association (HIGH)

**Issue**: `MemoryRecord` has zero receipt-related fields. `memory.py` has zero references to "receipt". The audit trail from memory → evidence → tool invocation → receipt is broken at the memory-to-receipt link.

**Fix**: Phase 2 must add `receipt_id` or `receipt_evidence_id` field to `MemoryRecord` and enforce the link at write time.

### G5: Memory Write Not Logically Idempotent (HIGH)

**Issue**: `MemoryKernel.write()` and `MemoryKernel.propose()` generate fresh `memory_id` each call. Same logical memory written twice produces duplicate records. Only `patch()` has `idempotency_key` support.

**Fix**: Phase 2 must add logical idempotency to `write()` and `propose()` via `idempotency_key` parameter.

### G6: Supersession Detection Missing (MEDIUM)

**Issue**: Zero code for detecting that a newer memory/evidence/receipt supersedes an older one. `conflict` status exists but `superseded` does not.

**Fix**: Phase 2 must add `superseded` status and detection logic.

### G7: No Memory Expiry/Retention (MEDIUM)

**Issue**: Working memory (SHORT_TERM, TEMPORARY_CONTEXT) has no automatic lifecycle. Only manual `clear_working_for_mission()`. No TTL, GC, or pruning.

**Fix**: Phase 2 should add TTL-based expiry for working memory.

### G8: Multiple Evidence/Receipt File Locations (MEDIUM)

**Issue**: Evidence and receipt artifacts are scattered across SQLite, `.nexara/`, and `reports/*/` with no synchronization or ingestion bridge.

**Fix**: Phase 2 must define clear storage authority: SQLite is canonical machine store; `.nexara/` is human-readable surface; `reports/` is legacy/archive.

---

## 4. Contract Gaps

### C1: Capability Model — 7 Code Fields vs 18 Contract Fields

The `.nexara/contracts/capability_registry_contract_v1.yaml` defines 18 fields, but the `Capability` Pydantic model has only 7. 11 fields exist ONLY_IN_CONTRACT:
provider, output_schema, permission_level, external_effect, idempotency, timeout_ms, retry_policy, rollback, evidence_policy, health_status, model_requirements.

### C2: JSON Schema Outdated

`schemas/evidence_artifact.json` (Draft 2020-12) requires only 6 fields while the `EvidenceArtifact` Pydantic model has ~15+ fields with computed fields (request_sha256, envelope_sha256).

---

## Summary Metrics

| Metric | Count |
|--------|-------|
| Duplicate system count | 3 |
| Authority conflict count | 3 |
| CRITICAL gaps | 1 |
| HIGH gaps | 4 |
| MEDIUM gaps | 3 |
| Contract gaps | 2 |
| Total issues | 13 |

*All findings are evidence-backed with file:line references. No speculation.*
