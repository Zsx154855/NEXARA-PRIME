# Knowledge-Memory Authority Contract V1

> NEXARA PRIME — Frozen Unified Contract for Knowledge, Memory, Evidence, and Recall
> Version: 1.0
> Gate: KMA Phase 1
> Frozen at: 2026-07-26
> Evidence HEAD: e38aae49dc545162e3cc652e554ea26c0b8278e5
> Status: CANONICAL — Phase 1 Freeze

## 1. Purpose

This contract freezes the canonical boundary between Knowledge, Memory, Evidence, and Recall in the NEXARA PRIME system. It defines what EXISTS, what is REUSED, what needs an ADAPTER, and what Phase 2 may create or modify.

All Phase 2 implementation MUST conform to this contract.

## 2. Domain Boundaries

### 2.1 Evidence Domain

| Property | Value |
|----------|-------|
| Canonical class | `EvidenceStore` (`src/nexara_prime/evidence.py`) |
| Model | `EvidenceArtifact` (`src/nexara_prime/models.py:309`) |
| Persistence | `SQLiteStore` — `records` table with `integrity_sha256` envelope |
| ID format | `evidence_{uuid4().hex[:12]}` or `evidence_{sha256(idempotency_key)[:12]}` |
| Write interface | `EvidenceStore.add(mission_id, kind, title, content, trace_id, ...)` |
| Read interface | `EvidenceStore.list(mission_id)` |
| Verification | `EvidenceStore.verify(evidence_id)` → bool |
| Idempotency | YES — via `idempotency_key` with replay/repair |
| Immutability | YES — append-only, no update/delete API |
| Phase 2 action | **REUSE directly** — no modifications needed |

### 2.2 Memory Domain

| Property | Value |
|----------|-------|
| Canonical class | `MemoryKernel` + `MemoryLayerManager` (`src/nexara_prime/memory.py`) |
| Model | `MemoryRecord` (`src/nexara_prime/models.py:389`) |
| Architecture | 4-layer: Working, Episodic, Semantic, Procedural |
| Persistence | `SQLiteStore` — `records` table (`memory`, `memory_candidate`, `memory_idempotency`, `memory_conflict` types) |
| ID format | `memory_{uuid4().hex[:12]}` |
| Write interface | `MemoryKernel.write(kind, key, content, trace_id, ...)` → `MemoryRecord` |
| Read interface | `MemoryKernel.inspect(mission_id)` → `list[dict]` |
| Idempotency | PARTIAL — only `patch()` has `idempotency_key` |
| Conflict detection | YES — `propose()` detects same-key-different-content |
| Evidence binding | YES — enforced for DECISION/FAILURE/FAILURE_EXPERIENCE/PATCH |
| Receipt binding | NO — Phase 2 must add |
| Phase 2 action | **ADAPTER needed** — add `idempotency_key` to `write()`, add `receipt_id` field |

### 2.3 Knowledge Domain

| Property | Value |
|----------|-------|
| Canonical class | `KnowledgeService` (`src/nexara_prime/knowledge.py`) |
| Model | Wraps `MemoryKernel.inspect()` — no separate model |
| Read interface | `KnowledgeService.query(kind_filter, key_filter)` → `list[dict]` |
| Phase 2 action | **REUSE directly** — add supersession detection |

### 2.4 Recall Domain

| Property | Value |
|----------|-------|
| Canonical class | `RAGPipeline` (`src/nexara_prime/rag_pipeline.py`) |
| Architecture | Ingest → Normalize → Chunk → Embed → Index → Retrieve → Rerank → Cite → Evaluate |
| Read interface | `RAGPipeline.query(query, top_k, layer_filter, ...)` |
| Memory sync | `MemoryLayerManager.sync_to_rag()` |
| Phase 2 action | **REUSE directly** — no modifications |

### 2.5 Capability Domain

| Property | Value |
|----------|-------|
| Canonical class | `CapabilityRegistry` (`src/nexara_prime/capabilities.py`) |
| Model | `Capability` (`src/nexara_prime/models.py:425`) |
| Phase 2 action | **FIX duplicates** — consolidate to single instance; add missing contract fields |

### 2.6 Admission Domain

| Property | Value |
|----------|-------|
| Canonical class | `ChiefBrainKernel` (`src/nexara_prime/chief_brain_kernel.py`) |
| Status | PARTIAL — class exists, NOT WIRED to runtime |
| Phase 2 action | **WIRE** — integrate `submit()` into `NexaraRuntime` mission lifecycle |

## 3. Reuse, Adapter, Migration Matrix

| Entity | Action | Details |
|--------|--------|---------|
| `EvidenceStore` | **REUSE** | No changes needed |
| `EvidenceArtifact` | **REUSE** | No changes needed |
| `MemoryKernel` | **ADAPTER** | Add `idempotency_key` to `write()`/`propose()`; add `receipt_id` to `MemoryRecord` |
| `MemoryLayerManager` | **REUSE** | No changes needed |
| `KnowledgeService` | **ADAPTER** | Add supersession detection |
| `RAGPipeline` | **REUSE** | No changes needed |
| `CapabilityRegistry` | **FIX** | Consolidate 2 instances → 1; add 11 missing contract fields |
| `ChiefBrainKernel` | **WIRE** | Integrate into runtime execution path |
| `Receipt` (new) | **CREATE** | New canonical `Receipt` Pydantic model |
| `cli.py` | **FIX** | Read `PROGRAM_STATE.json` instead of deprecated `PROJECT_STATE.json` |
| `schemas/evidence_artifact.json` | **UPDATE** | Sync with Pydantic model fields |
| `.nexara/evidence/` ingestion | **CREATE** | Bridge to ingest file-based evidence into SQLite EvidenceStore |

## 4. KMA Invariants

### KMA_INVARIANT_01: Single Canonical Authority
Each domain object has EXACTLY ONE canonical source of truth. No parallel stores. No shadow copies.

### KMA_INVARIANT_02: Evidence is Append-Only
Evidence cannot be modified or deleted after creation. `EvidenceStore` has no update/delete API.

### KMA_INVARIANT_03: Memory Requires Evidence
Committed memory records MUST have valid `source_evidence_id` referencing verified evidence (enforced for DECISION, FAILURE, FAILURE_EXPERIENCE, PATCH types when mission-scoped).

### KMA_INVARIANT_04: Recall is Read-Only
Knowledge queries and RAG retrieval MUST NOT modify memory or evidence. No write side-effects.

### KMA_INVARIANT_05: Human Approval for Conflicts
Conflicting memory records require `propose()` → human approve → `commit_candidate()` flow. No automatic conflict resolution.

### KMA_INVARIANT_06: Idempotent Writes
Memory and evidence writes MUST be idempotent via `idempotency_key`. Same logical operation repeated MUST return same result.

### KMA_INVARIANT_07: Machine Index is Derived
Search index is derived from Canonical Source and approved Memory. It MUST NOT become a parallel truth source. Damaged indexes can be rebuilt.

### KMA_INVARIANT_08: Obsidian is Human Surface
Obsidian vault (`docs/`) provides human-readable understanding. It CANNOT directly change runtime state, mission status, or memory content.

## 5. ID Rules

| Entity | Prefix | Format | Generator |
|--------|--------|--------|-----------|
| Evidence | `evidence_` | `evidence_{uuid4().hex[:12]}` or `evidence_{sha256(key)[:12]}` | `new_id("evidence")` |
| Memory | `memory_` | `memory_{uuid4().hex[:12]}` | `new_id("memory")` |
| Mission | `mission_` | `mission_{uuid4().hex[:12]}` | `new_id("mission")` |
| Receipt | `receipt_` | `receipt_{uuid4().hex[:12]}` | `new_id("receipt")` |
| Capability | `<type>.<name>` | e.g., `skill.mission_compilation` | CapabilityRegistry |
| Event | `evt_` | `evt_{sha256(key)[:12]}` | EvidenceStore |

All IDs are generated by `new_id(prefix)` in `src/nexara_prime/models.py:15`. No scattered ID generation.

## 6. Recall Gate Contract

### Input
- `query: str` — natural language query
- `layers: list[str] | None` — optional layer filter (working, episodic, semantic, procedural)
- `top_k: int` — max results (default 10)
- `mission_id: str | None` — optional mission scope

### Output
- `results: list[{doc_id, content, score, citation, evidence_ref, layer}]`
- Empty list if no matches (not an error)
- Falls back to keyword search when RAG unavailable

### Failure Semantics
- RAG unavailable → keyword fallback (graceful degradation)
- No results → empty list (not error)
- Invalid query → ValueError

## 7. Knowledge Commit Contract

### Admission Rules
1. `kind` MUST be valid `MemoryKind` enum value
2. `key` and `content` MUST be non-empty
3. `confidence` MUST be in [0.0, 1.0]
4. DECISION/FAILURE/FAILURE_EXPERIENCE/PATCH types REQUIRE `source_evidence_id` when mission-scoped
5. UNVERIFIED_INFERENCE CANNOT be committed — always routed to `propose()`
6. `idempotency_key` is REQUIRED for Phase 2 writes

### Conflict Semantics
- Same `key` + different `content` + `status=committed` → `conflict_keys` populated
- Status set to `conflict`
- Human approval required via `commit_candidate()`

### Supersession Semantics (Phase 2)
- `status: superseded` when a newer record with same key is committed
- Original record preserved; `superseded_by` field references replacement
- Superseded records excluded from default queries

### Freshness Semantics
- `confidence` indicates certainty (1.0 = verified, <1.0 = inferred)
- Time-decay weighting in RAG retrieval (half-life: 30 days default)
- No automatic expiry in Phase 1; Phase 2 adds TTL for working memory

## 8. Phase 2 Allowed Modifications

### Files Allowed
- `src/nexara_prime/chief_brain_kernel.py` — wire into runtime
- `src/nexara_prime/runtime.py` — integrate kernel admission, consolidate instances
- `src/nexara_prime/memory.py` — add idempotency, receipt link
- `src/nexara_prime/models.py` — add Receipt model, update MemoryRecord
- `src/nexara_prime/knowledge.py` — add supersession detection
- `src/nexara_prime/capabilities.py` — consolidate instances, add contract fields
- `src/nexara_prime/cli.py` — fix PROJECT_STATE reference
- `contracts/kma/` — NEW KMA contract files
- `schemas/` — update evidence schema, add new schemas
- `tests/` — NEW KMA tests
- `reports/kma/` — Phase 2 reports
- `evidence/kma/` — Phase 2 evidence

### Files Prohibited
- `.nexara/contracts/` — frozen, read-only
- `.nexara/evidence/` — immutable
- `.nexara/receipts/` — immutable
- `docs/` — Obsidian vault preserved
- `governance/` — NSEC supreme
- `experience/` — UI layer
- `platform/` — SDK
- `scripts/` — operational scripts
- Everything not in allowed scope

## 9. Dual-Mission Acceptance Criteria

### Mission A: KMA Phase 2 Implementation
1. ChiefBrainKernel wired into NexaraRuntime — admission gate enforced
2. MemoryKernel.write() and propose() accept idempotency_key
3. MemoryRecord has receipt_id field with enforced link
4. Canonical Receipt Pydantic model created
5. CapabilityRegistry consolidated to single instance
6. Capability model has all 18 contract fields
7. cli.py reads PROGRAM_STATE.json
8. Supersession detection implemented
9. Working memory auto-expiry implemented
10. All existing tests pass; new KMA tests pass
11. No duplicate systems remain
12. No authority conflicts remain

### Mission B: KMA Phase 2 Evidence
1. File-based evidence ingestion bridge to EvidenceStore
2. schemas/evidence_artifact.json synced with Pydantic model
3. All .legacy.bak files archived to docs/99-Legacy/
4. Deprecated PROJECT_STATE.json removed or deprecation header added
5. Evidence/receipt cross-references verified

## 10. Rollback Requirements

If Phase 2 changes break existing behavior:
1. `ChiefBrainKernel` wiring can be reverted to unwired state
2. `MemoryKernel` idempotency is additive — existing calls unaffected
3. `CapabilityRegistry` consolidation uses existing single-instance pattern
4. All Phase 2 changes are within allowed scope — no cascading rollback needed in prohibited files

## 11. Validation

- [x] No second Memory Store declared
- [x] No second Evidence Store declared
- [x] No second Receipt Store declared
- [x] Obsidian confirmed as human-readable surface
- [x] Machine Index confirmed as derived
- [x] Evidence remains append-only
- [x] Receipt is NEW creation, not replacement
- [x] Phase 2 scope explicitly bounded

---

> Contract frozen at Phase 1. All Phase 2 implementation MUST reference this document.
> Modifications to this contract require KMA Phase 3 amendment process.
