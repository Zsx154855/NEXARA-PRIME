# Knowledge-Memory Authority Contract V1.1 — Amendment

> NEXARA PRIME — Amendment to KMA Contract V1
> Version: 1.1
> Amends: KMA Contract V1.0 (frozen 2026-07-26)
> Frozen at: 2026-07-26
> Evidence HEAD: e38aae49dc545162e3cc652e554ea26c0b8278e5
> Status: CANONICAL — Phase 1.5 Amendment

## Amendment Scope

This amendment extends KMA Contract V1.0 based on findings from the independent Hermes Phase 1 read-only audit. It does NOT replace V1.0. Where V1.1 contradicts V1.0, V1.1 takes precedence.

## Amendment 1: EvidenceStore API Extension (Addresses Blocker B2)

### Section 2.1 (Evidence Domain) amended

**Change**: EvidenceStore Phase 2 action changed from "REUSE directly" to "EXTEND API".

**New API methods** (added to EvidenceStore in Phase 2):

| Method | Purpose |
|--------|---------|
| `get_by_id(evidence_id: str) → EvidenceArtifact \| None` | Public single-evidence lookup with integrity validation |
| `get_by_idempotency_key(key: str) → EvidenceArtifact \| None` | Public idempotency-key lookup using internal replay/repair |
| `get_envelope(evidence_id: str) → dict[str, Any] \| None` | Public integrity envelope access replacing raw store reads |
| `receipt_status(mission_id: str) → dict[str, Any]` | Single authority for receipt presence judgment |
| `find_by_idempotency(key: str) → dict[str, Any] \| None` | Public idempotency lookup replacing runtime bypass |

**New invariant**: KMA_INVARIANT_09 — No Raw Store Access. Runtime, Memory, Brain, Tools, CLI, and all other modules MUST NOT call `SQLiteStore` methods directly for evidence-type records. All evidence access MUST go through `EvidenceStore` public API.

## Amendment 2: Receipt Authority Clarification (Addresses Convergence C1)

### Section 2.4 (Receipt Domain) replaces previous Section 2.3 (Receipt) from V1.0

**Receipt IS an `EvidenceArtifact` with constrained `kind`.** No separate `ReceiptStore`. No separate `Receipt` Pydantic model.

| Property | Value |
|----------|-------|
| Canonical class | `EvidenceStore` — same as Evidence |
| Canonical model | `EvidenceArtifact` with `kind` ∈ `{execution_receipt, tool_receipt, completion_receipt, approval_receipt, command_receipt}` |
| Canonical hash | `sha256(content)` — same as Evidence |
| Self-reference rule | Receipt MUST NOT reference its own future commit SHA |
| Receipt status authority | `EvidenceStore.receipt_status(mission_id)` — SINGLE authority |
| Runtime judgment | PROHIBITED — `NexaraRuntime` MUST NOT independently judge `receipt_present` |
| File projection | `.nexara/receipts/*.json` — human-readable governance projection; NOT canonical store |
| Legacy files | `reports/*/RECEIPT.json` — historical artifacts; import or archive |
| Phase 2 action | **EXTEND EvidenceStore** — add `receipt_status()`; **REFACTOR runtime** — delegate to EvidenceStore |

**New invariant**: KMA_INVARIANT_10 — Single Receipt Judgment. Only `EvidenceStore.receipt_status()` may determine receipt presence. No other code path may independently judge whether a receipt exists.

## Amendment 3: Capability History Persistence (Addresses Blocker B3)

### Section 2.5 (Capability Domain) amended

**Change**: CapabilityRegistry Phase 2 action changed from "FIX duplicates" to "ADD PERSISTENCE + fix duplicates".

| Property | Value |
|----------|-------|
| Persistence | `SQLiteStore` — NEW `capability_history` record type |
| Raw records | Authoritative, persisted, append-only |
| Scores | Derived from raw records, cached in memory, recomputable on restart |
| Schema | `capability_id, mission_id, provider, model, success, failure_kind, latency_ms, input_tokens, output_tokens, cost, retry_count, recovery, evaluation_score, evidence_id, timestamp, schema_version, idempotency_key` |
| Restart recovery | Load raw records → recompute scores |
| Phase 2 action | **ADD PERSISTENCE** — add `SQLiteStore` dependency, persist raw records, recompute scores on startup |

**New invariant**: KMA_INVARIANT_11 — Capability History Persistence. Capability invocation outcomes MUST be persisted to SQLiteStore. Scores are derived from persisted raw records. Restart MUST NOT lose capability history.

## Amendment 4: ChiefBrainKernel Recall Integration (Addresses Blocker B1)

### Section 2.6 (Admission Domain) amended

**Change**: ChiefBrainKernel Phase 2 action extended to include recall.

| Property | Value |
|----------|-------|
| Recall dependency | `MemoryLayerManager` injected via constructor |
| Recall method | `ChiefBrainKernel.recall(query, layers, top_k, mission_id)` → delegates to `MemoryLayerManager.search()` |
| Prohibited | `ChiefBrainKernel` MUST NOT access `SQLiteStore` directly |
| Phase 2 action | **WIRE + ADD RECALL** — integrate `submit()` into runtime; add `recall()` delegate method |

## Amendment 5: KMA Runtime Types (Addresses Blocker B4)

### New Section 2.7 added

Four new Pydantic models added to `src/nexara_prime/models.py`:

| Type | Purpose | Key Fields |
|------|---------|------------|
| `KnowledgeObject` | Canonical entity representation | `object_id`, `object_type` (evidence/memory/receipt), `sha256`, `envelope_sha256`, `idempotency_key`, `status`, `confidence` |
| `KnowledgeRelation` | Edge between KnowledgeObjects | `relation_id`, `source_id`, `target_id`, `relation_type` (11 values) |
| `KnowledgeRecall` | Query input contract | `query`, `layers`, `top_k`, `min_confidence`, `include_candidates` |
| `KnowledgeCommit` | Write input contract | `kind` (MemoryKind), `key`, `content`, `idempotency_key`, `receipt_id` |

Existing `MemoryRecord` and `EvidenceArtifact` UNCHANGED. New types are additive.

## Amendment 6: CircuitBreaker Consolidation (Addresses Blocker B5)

### New Section 2.8 added

| Property | Value |
|----------|-------|
| Canonical implementation | `model_router.py::CircuitBreaker` (per-provider) |
| Removed in Phase 2 | `model_gateway.py::CircuitBreaker` (redundant single-provider) |
| Kept as-is | `connectors/health.py::CircuitBreaker` (different domain) |
| Phase 2 action | **CONSOLIDATE** — remove `model_gateway.py:63-91`; inject `ModelRouter`'s breaker into `ModelGateway` |

## Amendment 7: Updated ID Rules

Insert `capability_history` into Section 5 (ID Rules):

| Entity | Prefix | Format |
|--------|--------|--------|
| Capability History | `caphist_` | `caphist_{uuid4().hex[:12]}` |

## Amendment 8: Updated Phase 2 Allowed Files

Replace Section 8 (Phase 2 Allowed Modifications) with expanded list:

### Files Allowed (UPDATED)
- `src/nexara_prime/chief_brain_kernel.py` — wire into runtime + add recall()
- `src/nexara_prime/runtime.py` — integrate kernel admission, consolidate instances, delegate receipt, replace bypass calls
- `src/nexara_prime/evidence.py` — add get_by_id(), get_by_idempotency_key(), get_envelope(), receipt_status(), find_by_idempotency()
- `src/nexara_prime/memory.py` — add idempotency_key, replace bypass calls with EvidenceStore.get_envelope()
- `src/nexara_prime/models.py` — add KnowledgeObject, KnowledgeRelation, KnowledgeRecall, KnowledgeCommit types; add CapabilityHistory model; update MemoryRecord with receipt_id
- `src/nexara_prime/capabilities.py` — add SQLiteStore dependency, persist capability_history, consolidate instances
- `src/nexara_prime/knowledge.py` — add supersession detection, KnowledgeCommit validation
- `src/nexara_prime/model_gateway.py` — remove CircuitBreaker class (lines 63-91), accept optional breaker
- `src/nexara_prime/model_router.py` — expose breaker for ModelGateway injection
- `src/nexara_prime/cli.py` — replace PROJECT_STATE with PROGRAM_STATE
- `schemas/evidence_artifact.json` — sync with Pydantic model
- `tests/test_kma_*.py` (NEW) — KMA test suite
- `contracts/kma/` — Phase 1.5 deliverables
- `reports/kma/` — Phase 2 reports
- `evidence/kma/` — Phase 2 evidence

### Dual-Mission Acceptance Criteria (UPDATED)

**Mission A: KMA Phase 2 Implementation**
1. ChiefBrainKernel wired + recall() method — admission gate + recall enforced
2. MemoryKernel.write() and propose() accept idempotency_key
3. MemoryRecord has receipt_id field with enforced link
4. EvidenceStore has get_by_id(), get_by_idempotency_key(), get_envelope(), receipt_status(), find_by_idempotency()
5. runtime._get_evidence_by_idempotency() replaced with EvidenceStore.find_by_idempotency()
6. runtime._verify_completion() delegates receipt judgment to EvidenceStore.receipt_status()
7. memory.py bypass calls replaced with EvidenceStore.get_envelope()
8. CapabilityHistory persisted to SQLite, scores recomputed on restart
9. CapabilityRegistry consolidated to single instance
10. 4 KMA Pydantic types added to models.py
11. CircuitBreaker consolidated (model_gateway CB removed)
12. cli.py reads PROGRAM_STATE.json
13. Supersession detection implemented
14. Working memory auto-expiry implemented
15. All existing tests pass; new KMA tests pass
16. No duplicate systems remain
17. No authority conflicts remain

**Mission B: KMA Phase 2 Evidence**
1. File-based evidence ingestion bridge to EvidenceStore
2. schemas/evidence_artifact.json synced with Pydantic model
3. All .legacy.bak files archived to docs/99-Legacy/
4. Deprecated PROJECT_STATE.json removed or deprecation header added
5. Evidence/receipt cross-references verified

### New Invariants Summary

| # | Invariant | Source |
|---|-----------|--------|
| KMA_INVARIANT_09 | No Raw Store Access for evidence records | Amendment 1 |
| KMA_INVARIANT_10 | Single Receipt Judgment via EvidenceStore.receipt_status() | Amendment 2 |
| KMA_INVARIANT_11 | Capability History Persistence to SQLiteStore | Amendment 3 |
| KMA_INVARIANT_12 | KMA Runtime Types must implement JSON schemas exactly | Amendment 5 |
| KMA_INVARIANT_13 | Single CircuitBreaker for model providers | Amendment 6 |

---

> This amendment extends KMA Contract V1.0. Original V1.0 remains canonical for unamended sections.
> Both documents must be read together for complete Phase 2 guidance.
