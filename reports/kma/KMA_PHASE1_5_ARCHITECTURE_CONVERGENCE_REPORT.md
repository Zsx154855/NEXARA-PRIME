# KMA Phase 1.5 — Architecture Convergence Report

> NEXARA Knowledge-Memory Authority — Phase 2 Architecture Frozen
> Generated: 2026-07-26
> Base: KMA Phase 1 (HEAD e38aae4)
> Inputs: Claude Phase 1 Census + Hermes Independent Audit
> Status: CANONICAL — Phase 1.5 Freeze

## Executive Summary

This report freezes the Phase 2 implementation architecture by resolving 5 blockers identified by the Hermes independent read-only audit and 2 additional convergence issues. All decisions are evidence-backed from actual code at HEAD e38aae4.

**Result: 5 blockers resolved. 0 new stores. 1 Contract Amendment. Phase 2 scope precisely bounded.**

---

## Blocker Resolution Summary

| Blocker | Severity | Resolution | Phase 2 Action |
|---------|----------|-----------|----------------|
| B1: CBK no Recall Runtime | P1 | Inject MemoryLayerManager into CBK | Add `recall()` method delegating to injected `MemoryLayerManager.search()` |
| B2: Evidence Raw Store Bypass | P0 | EvidenceStore API extension | Add `get_by_id()`, `get_by_idempotency_key()`, `receipt_status()`; delete bypass calls |
| B3: Capability History memory-only | P0 | SQLiteStore persistence | Add `capability_history` record type; persist raw records; scores derived |
| B4: KMA Schemas no Python types | P1 | New Pydantic models | Create 4 lightweight types reusing existing enums/patterns |
| B5: CircuitBreaker triple impl | P1 | Consolidate model breakers | Merge model_gateway CB into model_router CB; keep connectors CB separate |
| C1: Receipt dual judgment | P1 | Single authority | `runtime._verify_completion()` delegates to `EvidenceStore.receipt_status()` |
| C2: Evidence init coordination | P2 | Explicit dependency | `EvidenceStore` receives all needed deps at init; no runtime DIY evidence reads |

---

## A. Unique Authority Freeze

See companion document: `reports/kma/KMA_PHASE1_5_UNIQUE_AUTHORITY_MAP.md`

9 domains frozen with single canonical authority each. 3 bypass paths to eliminate in Phase 2.

---

## B. Evidence Raw Store Bypass — Resolution

### Problem

8 bypass locations exist where code calls `SQLiteStore` methods directly for evidence-type records, circumventing `EvidenceStore`'s integrity envelope, idempotency guarantees, and verification chain:

| # | File | Line | Method | Severity |
|---|------|------|--------|----------|
| 1 | `runtime.py` | 825 | `self.store.find_record("evidence", ...)` | CRITICAL |
| 2 | `runtime.py` | 826 | `self.store.find_record_envelope("evidence", ...)` | CRITICAL |
| 3 | `memory.py` | 128 | `self.store.get_record_envelope(evidence_id)` | HIGH |
| 4 | `memory.py` | 137 | `self.store.get_record_envelope(evidence_id)` (fallback) | HIGH |
| 5 | `product_reality/evolution.py` | 150 | `self.evidence.store.get_record_envelope(...)` | HIGH |
| 6 | `cli.py` | 142 | `store.list_records("evidence", ...)` | MEDIUM |
| 7 | `db.py` | 137 | evidence-specific migration logic | INFO |
| 8 | `db.py` | 305 | evidence-specific origin_sha256 backfill | INFO |

### Resolution

**Rule**: Runtime, Memory, Brain, Tools, CLI, and all other modules MUST NOT call `SQLiteStore` methods directly for evidence-type records. All evidence access MUST go through `EvidenceStore` public API.

**Phase 2 EvidenceStore API Extensions** (new methods to add):

```python
class EvidenceStore:
    # Existing (unchanged):
    # add(), verify(), list(), is_preverified_and_integrity_bound(),
    # verify_receipt_chain(), verify_all(), state_change()

    # NEW in Phase 2:
    def get_by_id(self, evidence_id: str) -> EvidenceArtifact | None:
        """Return validated EvidenceArtifact by ID. Raises KeyError if not found."""

    def get_by_idempotency_key(self, key: str) -> EvidenceArtifact | None:
        """Return evidence by idempotency key. Uses internal replay/repair."""

    def get_envelope(self, evidence_id: str) -> dict[str, Any] | None:
        """Return integrity envelope for an evidence record. Public wrapper around store."""

    def receipt_status(self, mission_id: str) -> dict[str, Any]:
        """Single authority for receipt presence. Returns {status, receipt_id, verifiable, gaps}."""

    def find_by_idempotency(self, key: str) -> dict[str, Any] | None:
        """Public idempotency-key lookup replacing runtime._get_evidence_by_idempotency()."""
```

**Phase 2 Deletions** (bypass calls to remove/replace):

| File | Line(s) | Replacement |
|------|---------|-------------|
| `runtime.py` | 825-826 | Call `self.evidence.find_by_idempotency(key)` |
| `memory.py` | 128, 137 | Call `self.evidence.get_envelope(evidence_id)` or `self.evidence.is_preverified_and_integrity_bound(evidence_id)` |
| `evolution.py` | 150 | Call `self.evidence.get_envelope(evidence_id)` |
| `cli.py` | 142 | Call `runtime.evidence.list(mission_id)` |

**Bypass paths NOT requiring Phase 2 changes** (infrastructure, not bypass):
- `db.py:137,305` — Internal migration logic necessary for store function. No change needed.
- `memory.py:137` fallback — When `self.evidence is None`, store is the only option. Acceptable.

---

## C. Unique Call Chain Freeze

### Canonical Mission Lifecycle

```
Human Intent
  → MissionTriageEngine.triage()
  → MissionCompiler.compile()
  → ChiefBrainKernel.submit()                    ← NEW: admission gate
      ├── validate_transition()                   ← state machine check
      ├── assert_no_self_verify()                 ← PROHIBIT_01
      ├── assert_no_permission_grant()            ← PROHIBIT_03
      ├── assert_evidence_not_modified()          ← PROHIBIT_04
      └── assert_full_completion_chain()          ← PROHIBIT_05
  → KnowledgeRecall (optional)                   ← NEW: kernel delegates recall
      └── MemoryLayerManager.search()
           ├── RAGPipeline.query()                ← semantic search
           └── MemoryKernel.inspect()             ← keyword fallback
  → Evidence validation (if recall returns results)
      └── EvidenceStore.get_by_id()               ← NEW: public read API
      └── EvidenceStore.verify()                  ← integrity check
  → Conflict / Supersession detection
      └── MemoryKernel.propose()                  ← conflict detection
      └── KnowledgeService.query()                ← supersession check (NEW)
  → Mission Contract
      └── ContractEngine.create()
  → Runtime Execution
      └── NexaraRuntime.run_mission()             ← KernelExecutionGuard enforced
          ├── ToolRuntime.invoke()
          │     └── ToolInvocation.receipt_evidence_id ← evidence link
          ├── EvidenceStore.add()                 ← tool evidence
          └── EvidenceStore.state_change()        ← state transitions
  → Evaluation
      └── EvaluationEngine.evaluate()
  → Memory Candidate
      └── MemoryKernel.propose()                  ← candidate with evidence backing
      └── MemoryKernel.commit_candidate()         ← human approval
  → KnowledgeCommit
      └── MemoryKernel.write()                    ← idempotent write (NEW)
  → Receipt Verification
      └── EvidenceStore.verify_receipt_chain()    ← chain integrity
      └── EvidenceStore.receipt_status()          ← NEW: single receipt authority
  → Mission Completion
      └── NexaraRuntime._verify_completion()
           └── EvidenceStore.receipt_status()     ← NEW: delegates, doesn't self-judge
```

### Responsibility Boundaries

| Component | Responsible For | Prohibited From |
|-----------|----------------|-----------------|
| **ChiefBrainKernel** | Mission admission, invariant enforcement, governance gate, recall delegation | Direct SQLite access, self-verification, permission grant, evidence modification |
| **NexaraRuntime** | Mission lifecycle execution, state transitions, tool orchestration | Bypassing kernel admission, self-judging receipt status, direct evidence store access |
| **EvidenceStore** | Evidence CRUD, integrity verification, idempotency, receipt chain, receipt status | Modification after creation, self-referencing future commits |
| **MemoryKernel** | Memory write/read, conflict detection, evidence binding, idempotency | Direct evidence store access (use EvidenceStore public API), self-committing unverified inferences |
| **KnowledgeService** | Unified query, kind/key filtering, supersession detection | Modifying memory or evidence, becoming parallel authority |
| **CapabilityRegistry** | Capability registration, scoring, history persistence, routing data | Creating second capability store, losing history on restart |

---

## D. Receipt — Single Source of Truth

### Decision

**Receipt IS an `EvidenceArtifact` with constrained `kind`.** No separate `ReceiptStore`. No separate `Receipt` Pydantic model.

### Canonical Receipt Definition

| Attribute | Value |
|-----------|-------|
| **Receipt kind values** | `execution_receipt`, `tool_receipt`, `completion_receipt`, `approval_receipt`, `command_receipt` |
| **Canonical Store** | `EvidenceStore` — same SQLite `evidence` record type |
| **Canonical Hash** | `sha256(content)` — same as all evidence |
| **Self-Reference Exclusion** | Receipt MUST NOT reference its own future commit SHA; `evidence_subject_head` is git SHA of the code being verified, not the receipt itself |
| **Mission Association** | `mission_id` field — same as all evidence |
| **Tool Association** | `tool_invocation_id` field — links to `ToolInvocation` |
| **Evaluation Association** | `parent_evidence` includes evaluation evidence |
| **Completion Association** | `verify_receipt_chain(mission_id)` audits complete chain |

### External Receipt Import

`.nexara/receipts/*.json` files are **human-readable governance projections**. They are NOT the canonical receipt store. Import path: read `.json` → `EvidenceStore.add(kind="completion_receipt", ...)` → stored in SQLite.

### File Projection vs SQLite Authority

| Location | Status | Authority |
|----------|--------|-----------|
| SQLite `evidence` records | **CANONICAL** | Single source of receipt truth |
| `.nexara/receipts/*.json` | **PROJECTION** — human-readable export | Read-only mirror; may lag behind canonical |
| `reports/*/RECEIPT.json` | **LEGACY** — historical artifacts | Not authoritative; import or archive |
| `ToolInvocation.receipt_evidence_id` | **REFERENCE** — foreign key to canonical | Points to SQLite evidence record |

### Prohibited Runtime Behavior

- `NexaraRuntime._verify_completion()` MUST NOT independently judge `receipt_present`
- MUST call `EvidenceStore.receipt_status(mission_id)` for single authoritative receipt judgment
- `runtime.py:882-909` must be refactored to delegate

---

## E. Capability History — Persistent Model

### Decision

Reuse `SQLiteStore` (same database, new record type). No separate database.

### Schema

```yaml
record_type: capability_history
record_id: caphist_{uuid4().hex[:12]}
columns:
  capability_id: str       # e.g., "skill.mission_compilation"
  mission_id: str | None   # parent mission
  provider: str            # e.g., "deepseek-v4-pro"
  model: str               # e.g., "deepseek-v4-pro"
  success: bool            # invocation outcome
  failure_kind: str | None # FailureCode enum value if failed
  latency_ms: float        # observed latency
  input_tokens: int        # prompt tokens
  output_tokens: int       # completion tokens
  cost: float              # USD cost
  retry_count: int         # retries before this outcome
  recovery: bool           # whether recovery was triggered
  evaluation_score: float | None  # from EvaluationEngine
  evidence_id: str | None  # link to EvidenceArtifact
  timestamp: str           # ISO-8601 UTC
  schema_version: int      # = 1
  idempotency_key: str     # for idempotent write
```

### Score Derivation

`CapabilityScore` (historical_success_rate, average_latency_ms, average_token_cost, recent_failure_rate, confidence, evidence_count) is **DERIVED** from raw `capability_history` records. Scores are recomputed on demand via `CapabilityRegistry._recompute_scores()`.

- **Raw records**: authoritative, persisted, immutable
- **Scores**: derived, cached in memory, recomputable from raw records on restart

### Restart Recovery

1. `CapabilityRegistry.__init__()` loads raw records from `SQLiteStore.list_records("capability_history")`
2. `_recompute_scores()` rebuilds all `CapabilityScore` objects from raw records
3. Cache is warm after startup

### Aggregation Rules

- `historical_success_rate` = successful / total (lifetime)
- `recent_failure_rate` = failed / total (last 100 records, or time-windowed)
- `average_latency_ms` = mean of last 100 records
- `average_token_cost` = mean cost of last 100 records
- `confidence` = weighted by evidence_count and recency

### Retention

- Default: keep all records (append-only)
- Optional: prune records older than 90 days, keeping aggregate statistics

### Migration

- Phase 2: add `capability_history` record type to `SQLiteStore._init_schema()`
- No alteration of existing tables needed
- `_mission_history` dict retained as write-through cache; migration is additive

---

## F. KMA Python Runtime Types

### Decision

Create 4 new Pydantic models in `src/nexara_prime/models.py`. Reuse existing `NModel` base, `new_id()`, `now_iso()`, `MemoryKind` enum, `ConfigDict`. Do NOT create separate `kma_models.py`.

Existing `MemoryRecord` and `EvidenceArtifact` remain as-is — they are application-layer types. New KMA types are contract-layer types that may wrap them.

### Type Mapping

#### KnowledgeObject

```python
class KnowledgeObject(NModel):
    """Canonical representation of any entity in the KMA system."""
    object_id: str                        # {prefix}_{uuid_hex}
    object_type: Literal["evidence", "memory", "receipt"]
    mission_id: str | None = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str | None = None
    sha256: str | None = None             # content hash
    envelope_sha256: str | None = None    # integrity envelope hash
    idempotency_key: str | None = None
    source_event_id: str | None = None
    trace_id: str = ""
    provenance: str = "runtime"           # runtime|human|import|migration|recovery
    status: str = "committed"             # committed|candidate|conflict|superseded|pending_review|cleared|unverified|verified|corrupt
    superseded_by: str | None = None
    confidence: float = 1.0               # 0.0-1.0
    verified: bool = False
    canonical: bool = False
    # Reuses: new_id("kobj"), now_iso(), NModel base
```

#### KnowledgeRelation

```python
class KnowledgeRelation(NModel):
    """Edge between two KnowledgeObjects."""
    relation_id: str = Field(default_factory=lambda: new_id("rel"))
    source_id: str                        # object_id of source
    target_id: str                        # object_id of target
    relation_type: Literal[
        "evidence_backing", "receipt_attests", "memory_derived_from",
        "supersedes", "conflicts_with", "references",
        "parent_of", "child_of", "depends_on", "produced_by", "verified_by"
    ]
    mission_id: str | None = None
    created_at: str = Field(default_factory=now_iso)
    confidence: float = 1.0
    evidence_id: str | None = None
    bidirectional: bool = False
    weight: float = 1.0                  # 0.0-1.0
```

#### KnowledgeRecall

```python
class KnowledgeRecall(NModel):
    """Query input for knowledge retrieval."""
    query: str                            # natural language query (minLength=1)
    layers: list[Literal["working", "episodic", "semantic", "procedural"]] | None = None
    top_k: int = 10                       # 1-100
    mission_id: str | None = None
    min_confidence: float = 0.3           # 0.0-1.0
    include_candidates: bool = False
    include_superseded: bool = False
    trace_id: str = ""
```

#### KnowledgeCommit

```python
class KnowledgeCommit(NModel):
    """Write input for committing knowledge to memory."""
    kind: MemoryKind                      # reuses existing enum (12 values)
    key: str                              # minLength=1
    content: str                          # minLength=1
    trace_id: str
    mission_id: str | None = None
    source_evidence_id: str | None = None
    idempotency_key: str | None = None    # REQUIRED in Phase 2
    confidence: float = 1.0              # 0.0-1.0; <0.8 routes to propose()
    receipt_id: str | None = None         # Phase 2 addition
    auto_commit: bool = False
    provenance: str = "runtime"
```

### Reuse vs New

| Existing Type | Relationship to KMA Types |
|---------------|---------------------------|
| `MemoryRecord` | Application-layer type. NOT modified. Can be constructed from `KnowledgeObject` with `object_type="memory"`. |
| `EvidenceArtifact` | Application-layer type. NOT modified. Can be constructed from `KnowledgeObject` with `object_type="evidence"`. |
| `MemoryKind` | REUSED directly by `KnowledgeCommit.kind`. |
| `new_id()`, `now_iso()`, `NModel` | REUSED by all 4 new types. |

### File Placement

All 4 types added to `src/nexara_prime/models.py`, after existing `MemoryRecord` definition (~line 406). Follow existing naming conventions (`NModel`, `ConfigDict`, `Field`).

### Backward Compatibility

- New types are additive — no existing types modified
- Existing `MemoryRecord` and `EvidenceArtifact` unchanged
- New types may be used alongside existing types; conversion helpers may be added later

---

## G. CircuitBreaker Convergence

### Finding

Three independent `CircuitBreaker` implementations exist:

| # | File | Per-Provider | Half-Open | Used By |
|---|------|-------------|-----------|---------|
| 1 | `model_gateway.py:63` | NO | NO | `ModelGateway` |
| 2 | `model_router.py:68` | YES | NO | `ModelRouter` |
| 3 | `connectors/health.py:9` | YES | YES | `ConnectorHealthMonitor` |

Implementation #1 and #2 serve the same purpose (model provider circuit breaking) and can fire sequentially on the same request (ModelRouter checks → ModelGateway checks).

### Decision

**Consolidate model_gateway.py CircuitBreaker into model_router.py CircuitBreaker.**

- **Phase 2**: Remove `model_gateway.py::CircuitBreaker` class
- **Phase 2**: `ModelGateway.__init__()` accepts optional `breaker: CircuitBreaker | None` parameter
- **Phase 2**: `NexaraRuntime` passes `ModelRouter`'s breaker to `ModelGateway`
- **Keep**: `connectors/health.py::CircuitBreaker` — different domain (connector health), different semantics (half-open), independent subsystem

### Single Authority

| Attribute | Value |
|-----------|-------|
| **Canonical Implementation** | `model_router.py::CircuitBreaker` + `CircuitBreakerState` |
| **Owner** | `ModelRouter` |
| **Granularity** | Per-provider (keyed by provider name string) |
| **State** | In-memory (no persistence needed — circuit state is ephemeral operational state) |
| **Runtime Call Chain** | `ModelRouter.route()` checks breaker → selects provider → `ModelGateway.complete()` → `ModelRouter.track_result()` updates breaker |
| **Phase 2 Deletion** | `model_gateway.py:63-91` (lines 63-91, CircuitBreaker class) |

### Rationale

1. `model_router.py`'s CircuitBreaker is strictly more capable (per-provider tracking)
2. They serve the same conceptual purpose (model provider circuit breaking)
3. Having two breakers on the same request path creates dual-tracking confusion
4. `connectors/health.py`'s CircuitBreaker is in a different domain and should NOT be merged

---

## H. Phase 2 Exact File Boundary

### Allowlist

| File | Modification | Blocks | Tests | Rollback |
|------|-------------|--------|-------|----------|
| `src/nexara_prime/chief_brain_kernel.py` | Add `recall()` method, inject `MemoryLayerManager`, wire into runtime admission path | B1, G1 | `test_kma_cbk_recall.py` | Remove `recall()` method, revert `__init__` |
| `src/nexara_prime/runtime.py` | Integrate `ChiefBrainKernel.submit()`, consolidate `CapabilityRegistry`/`TokenCompiler` instances, delegate receipt to `EvidenceStore.receipt_status()`, replace bypass calls | B2, C1, D1, D2, G1 | `test_kma_runtime_integration.py` | Remove CBK wiring, restore dual instances |
| `src/nexara_prime/evidence.py` | Add `get_by_id()`, `get_by_idempotency_key()`, `get_envelope()`, `receipt_status()`, `find_by_idempotency()` methods | B2, C1 | `test_kma_evidence_api.py` | Remove new methods (no existing callers) |
| `src/nexara_prime/memory.py` | Add `idempotency_key` to `write()`/`propose()`, replace bypass calls with `EvidenceStore.get_envelope()`, add `receipt_id` to `MemoryRecord` | B2, G4, G5 | `test_kma_memory_idempotency.py` | Remove new params (backward compat) |
| `src/nexara_prime/models.py` | Add 4 KMA types (`KnowledgeObject`, `KnowledgeRelation`, `KnowledgeRecall`, `KnowledgeCommit`), add `CapabilityHistory` model, update `MemoryRecord` with `receipt_id` field | B3, B4, G2 | `test_kma_types.py` | Remove new types (no existing callers) |
| `src/nexara_prime/capabilities.py` | Add `SQLiteStore` dependency, persist `capability_history`, add `_recompute_scores()`, add `get_history()`/`get_aggregates()`, consolidate duplicate instances | B3, D1 | `test_kma_capability_persistence.py` | Revert to in-memory-only |
| `src/nexara_prime/knowledge.py` | Add supersession detection to `query()`, add `KnowledgeCommit` validation | B4, G6 | `test_kma_knowledge.py` | Remove supersession (additive) |
| `src/nexara_prime/model_gateway.py` | Remove `CircuitBreaker` class (lines 63-91), accept optional breaker from constructor | B5 | `test_kma_circuitbreaker.py` | Restore local CircuitBreaker |
| `src/nexara_prime/model_router.py` | Accept external breaker injection, expose breaker for ModelGateway | B5 | — (existing behavior preserved) | Revert to self-contained breaker |
| `src/nexara_prime/cli.py` | Replace PROJECT_STATE references with PROGRAM_STATE | A1 | — (existing CLI tests) | Revert to PROJECT_STATE |
| `tests/test_kma_*.py` (NEW) | New KMA test suite: CBK recall, Evidence API, Memory idempotency, Capability persistence, CircuitBreaker, Types, Runtime integration | ALL | — (self-testing) | Delete new test files |
| `schemas/evidence_artifact.json` | Sync with Pydantic model fields | C2 | — (schema validation) | Revert schema |
| `contracts/kma/` (NEW/AMEND) | Phase 1.5 deliverables | — | Self-documenting | N/A |

### Denylist (PROHIBITED)

| File/Directory | Reason |
|----------------|--------|
| `.nexara/contracts/` | Frozen at G1 |
| `.nexara/evidence/` | Immutable evidence |
| `.nexara/receipts/` | Immutable receipts |
| `docs/` | Obsidian vault preserved |
| `governance/` | NSEC supreme |
| `experience/` | UI layer |
| `platform/` | SDK |
| `scripts/` | Operational scripts |
| `src/nexara_prime/db.py` | Infrastructure — no KMA changes needed (internal migration already handles new record types) |
| `src/nexara_prime/orchestration.py` | Separate domain — receives EvidenceStore via constructor, no bypass found |
| `src/nexara_prime/api.py` | API layer — shouldn't change; one bypass (health) fixed in CLI |
| Any file not in allowlist | Out of scope |

---

## Validation

- [x] Unique Authority per domain — 9 domains, 0 ambiguities
- [x] Receipt is constrained EvidenceArtifact — NO second ReceiptStore
- [x] Evidence Raw Store Bypass resolved — 6 bypass deletions, 2 infrastructure exceptions
- [x] Capability History persistent model defined — SQLiteStore, not separate DB
- [x] KMA 4 Python types mapped — Pydantic, existing models reused
- [x] CircuitBreaker consolidated — model_gateway CB merged into model_router CB
- [x] Phase 2 allowlist precise — 12 files, each with purpose/blocker/test/rollback
- [x] No existing product code modified
- [x] No commits, pushes, deploys

---

> Architecture frozen. Phase 2 implementation must conform to all decisions herein.
> Deviations require KMA Phase 3 amendment process.
