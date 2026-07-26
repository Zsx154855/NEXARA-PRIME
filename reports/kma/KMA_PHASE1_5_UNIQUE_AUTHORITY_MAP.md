# KMA Phase 1.5 — Unique Authority Map

> NEXARA Knowledge-Memory Authority — Phase 2 Unique Authority Freeze
> Generated: 2026-07-26
> Base: KMA Phase 1 Asset Inventory (HEAD e38aae4)
> Status: CANONICAL — Phase 1.5 Freeze

## Principle

**Single Source of Truth per domain. No parallel authorities. No bypass paths.**

Every domain has EXACTLY ONE canonical authoritative source. Derivations, caches, projections, and human-readable surfaces are explicitly labeled as non-authoritative.

---

## 1. Mission State Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `NexaraRuntime` (`src/nexara_prime/runtime.py`) |
| **Public API** | `NexaraRuntime.create_mission()`, `plan_mission()`, `approve_mission()`, `run_mission()` |
| **State Machine** | `MissionStateMachine` (`state_machine.py`) — validates ALL state transitions |
| **Prohibited Bypass** | Direct SQLite write to `mission` record type; CLI direct manipulation; Obsidian docs claiming mission authority |
| **Derived Index** | `list_mission()` reads from SQLite via `self.store.list_records("mission")` — internal projection only |
| **Cache** | None — mission state is authoritative, not cached |
| **Projection** | API response JSON, CLI output — read-only snapshots |
| **Recovery Authority** | `DurableRecovery` (`recovery.py`) — checkpoints mission state to `mission_checkpoint` record type |
| **Verification Authority** | `MissionStateMachine.transition()` — validates before every state change |

## 2. Runtime Memory Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `MemoryKernel` + `MemoryLayerManager` (`src/nexara_prime/memory.py`) |
| **Public API** | `MemoryKernel.write()`, `propose()`, `patch()`, `commit_candidate()`, `inspect()`, `candidates()` |
| **Persistence** | `SQLiteStore` — `memory`, `memory_candidate`, `memory_idempotency`, `memory_conflict` record types |
| **Prohibited Bypass** | Direct SQLite write to memory record types; direct read bypassing `inspect()` |
| **Derived Index** | `RAGPipeline` — search index rebuilt from committed memory; `KnowledgeService.query()` — filtered projection |
| **Cache** | `RAGPipeline` embedding cache — derived, rebuildable |
| **Projection** | Obsidian docs referencing memory concepts — human-readable, not authoritative |
| **Recovery Authority** | `MemoryKernel.verify_evidence_binding()` — audits integrity; recovery from evidence is Phase 2 |
| **Verification Authority** | `EvidenceStore.verify()` for evidence backing; `MemoryKernel.verify_evidence_binding()` for cross-check |

## 3. Evidence Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `EvidenceStore` (`src/nexara_prime/evidence.py`) — SINGLE authority, NO bypass |
| **Public API** | `EvidenceStore.add()`, `verify()`, `list()`, `is_preverified_and_integrity_bound()`, `verify_receipt_chain()`, `verify_all()`, `state_change()`, **NEW for Phase 2: `get_by_id()`, `get_by_idempotency_key()`, `receipt_status()`** |
| **Persistence** | `SQLiteStore` — `evidence` record type with `integrity_sha256` + `origin_sha256` envelope |
| **Prohibited Bypass** | **BLOCKED**: `runtime._get_evidence_by_idempotency()` (runtime.py:825-826) — bypasses EvidenceStore, uses direct SQLite queries. **BLOCKED**: any `self.store.find_record("evidence", ...)` call outside evidence.py. **BLOCKED**: any `self.store.save_record(..., "evidence", ...)` call outside evidence.py. |
| **Derived Index** | `list()` projection — read-only, non-authoritative |
| **Cache** | None — evidence is authoritative, not cached |
| **Projection** | `.nexara/evidence/*.md` — human-readable export of evidence summaries; NOT the canonical store |
| **Recovery Authority** | `EvidenceStore.replay_and_repair_event()` — repairs missing events from stored evidence |
| **Verification Authority** | `EvidenceStore.verify()` — sha256(content) + envelope_sha256 + origin projection validation |

## 4. Receipt Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `EvidenceStore` — Receipt IS an `EvidenceArtifact` with `kind` in `{execution_receipt, tool_receipt, completion_receipt, approval_receipt, command_receipt}`. **NO separate ReceiptStore.** |
| **Public API** | `EvidenceStore.add(mission_id, "execution_receipt", ...)`, `EvidenceStore.verify_receipt_chain(mission_id)`, **NEW: `EvidenceStore.receipt_status(mission_id)`** → `{status: "present"|"missing"|"unverifiable", ...}` |
| **Canonical Model** | `EvidenceArtifact` with `kind` constraint + `receipt_evidence_id` on `ToolInvocation` |
| **Identification** | Receipt `evidence_id` = `evidence_{uuid}` (same format as all evidence) |
| **Self-Reference Exclusion** | Runtime MUST NOT infer `receipt_present`; must call `EvidenceStore.receipt_status()` |
| **File Projection** | `.nexara/receipts/*.json` — human-readable governance surface; NEVER the canonical receipt store |
| **Legacy Files** | `reports/*/RECEIPT.json` — historical artifacts; NOT authoritative |
| **Prohibited Bypass** | **BLOCKED**: `runtime._verify_completion()` (runtime.py:882-909) — independently judges `receipt_present`; must delegate to `EvidenceStore.receipt_status()` |
| **Recovery Authority** | `EvidenceStore.replay_and_repair_event()` applies to receipt evidence too |
| **Verification Authority** | `EvidenceStore.verify_receipt_chain()` — single authority for receipt chain integrity |

## 5. Capability History Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `CapabilityRegistry` (`src/nexara_prime/capabilities.py`) — **Phase 2 must add SQLiteStore persistence** |
| **Public API** | `CapabilityRegistry.register()`, `register_v2()`, `update_score()`, `get_score()`, `list_capable()`, `list_all()`, **NEW: `get_history()`, `get_aggregates()`** |
| **Persistence** | **Phase 2 must add**: `capability_history` record type in SQLiteStore; schema: capability_id, mission_id, provider, model, success, failure_kind, latency_ms, input_tokens, output_tokens, cost, retry_count, recovery, evaluation_score, evidence_id, timestamp, schema_version, idempotency_key |
| **Current State** | `_mission_history: dict[str, list[dict]]` — IN-MEMORY ONLY, lost on restart. `_scores: dict[str, CapabilityScore]` — IN-MEMORY ONLY, recomputed from empty on restart. |
| **Derived State** | `CapabilityScore` (historical_success_rate, average_latency_ms, average_token_cost, recent_failure_rate, confidence) — DERIVED from `_mission_history` raw records; recomputable on restart once raw records are persisted |
| **Cache** | Running score values can be cached; authoritative raw records must be persisted |
| **Projection** | `list_capable()` — projection filtered by capability + confidence threshold |
| **Recovery Authority** | After Phase 2 persistence: rebuild scores from persisted capability_history records |
| **Verification Authority** | Cross-reference with `EvidenceStore` via `evidence_id` field |

## 6. Chief Brain Admission Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `ChiefBrainKernel` (`src/nexara_prime/chief_brain_kernel.py`) |
| **Public API** | `ChiefBrainKernel.submit(mission_id, caller, ...)` → `KernelAdmissionContext`; `KernelExecutionGuard.assert_admitted(ctx)` |
| **Recall Path** | `ChiefBrainKernel` → `KnowledgeService.query()` or `MemoryLayerManager.search()` — kernel delegates recall, does NOT own it |
| **Prohibited Bypass** | Direct runtime execution without `submit()`; `NexaraRuntime` bypassing kernel to create/plan/approve/run |
| **Prohibited Direct Access** | `ChiefBrainKernel` MUST NOT access `SQLiteStore` directly. All evidence access through `EvidenceStore`. All memory access through `MemoryKernel`. |
| **Cache** | Admission context is ephemeral — no persistence of admission records beyond mission state |
| **Projection** | Admission results visible through mission state transitions |
| **Recovery Authority** | Admission is per-mission-call; recovery replays mission lifecycle, which re-enters admission gate |
| **Verification Authority** | `KernelExecutionGuard.assert_admitted()` — gate enforced by runtime before execution |

## 7. Knowledge Recall Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Store** | `RAGPipeline` (`src/nexara_prime/rag_pipeline.py`) + `KnowledgeService` (`src/nexara_prime/knowledge.py`) |
| **Public API** | `MemoryLayerManager.search(query, layers, top_k, mission_id)` → semantic search; `KnowledgeService.query(kind_filter, key_filter)` → filtered query |
| **Backend** | `RAGPipeline` (embedding + retrieval) with `keyword_search` fallback via `MemoryKernel.inspect()` |
| **Prohibited Bypass** | Direct SQLite query to memory records for search purposes |
| **Derived Index** | RAG embedding index — derived from committed memory; rebuildable via `MemoryLayerManager.sync_to_rag()` |
| **Cache** | Embedding cache — derived, rebuildable |
| **Projection** | Search results projected as `{doc_id, content, score, citation, evidence_ref, layer}` |
| **Recovery Authority** | Index can be fully rebuilt from `MemoryKernel.inspect()` + `sync_to_rag()` |

## 8. Obsidian Human-Readable Projection

| Attribute | Value |
|-----------|-------|
| **Status** | **NOT authoritative** for any runtime domain |
| **Role** | Human understanding, design, decision tracking, ADR |
| **Source** | `docs/` — Git-backed Markdown vault |
| **Audience** | Human operators, reviewers, architects |
| **Prohibited** | Changing mission state, writing to memory, creating/verifying evidence |

## 9. Machine-Readable Derived Index

| Attribute | Value |
|-----------|-------|
| **Status** | **Derived**, NOT authoritative |
| **Source** | Committed `MemoryRecord`s in SQLite |
| **Role** | Fast semantic search |
| **Rebuild** | `MemoryLayerManager.sync_to_rag()` — fully rebuildable |
| **Prohibited** | Becoming a parallel truth source; surviving independently of canonical memory |

---

## Authority Validation Matrix

| Domain | Single Store? | Bypass Paths? | Persisted? | Recovery? |
|--------|--------------|--------------|------------|-----------|
| Mission State | YES | 0 | YES (SQLite) | YES (checkpoints) |
| Runtime Memory | YES | 0 | YES (SQLite) | PARTIAL |
| Evidence | YES | **1 bypass** (runtime.py:825) | YES (SQLite) | YES |
| Receipt | YES (via Evidence) | **1 dual judgment** (runtime.py:882) | YES (SQLite) | YES |
| Capability History | YES | 0 | **NO (P0)** | NO |
| Chief Brain Admission | YES | **1 bypass** (runtime bypasses kernel) | PARTIAL | YES |
| Knowledge Recall | YES | 0 | YES (derived) | YES (rebuild) |
| Obsidian | YES | 0 | N/A | N/A |
| Machine Index | YES (derived) | 0 | YES (derived) | YES (rebuild) |

---

> All claims verified against code at HEAD e38aae4. Phase 2 must resolve 3 bypass/dual-judgment paths.
