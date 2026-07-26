# KMA Runtime Type Mapping V1

> NEXARA PRIME — Python Runtime Type Mapping for KMA JSON Schemas
> Version: 1.0
> Frozen at: 2026-07-26
> Status: CANONICAL — Phase 1.5 Freeze

## Overview

This document maps the 4 KMA JSON Schemas (Phase 1) to concrete Python Pydantic models for Phase 2 implementation. All types are added to `src/nexara_prime/models.py`.

## Reuse Policy

| Artifact | Reuse? | Rationale |
|----------|--------|-----------|
| `NModel` base class | YES | Existing Pydantic base with `ConfigDict(extra="forbid")` |
| `new_id(prefix)` | YES | Centralized ID generation |
| `now_iso()` | YES | Centralized timestamp |
| `MemoryKind` enum | YES | 12 values, identical to KnowledgeCommit.kind |
| `ConfigDict` | YES | Pydantic config |
| `Field` | YES | Pydantic field defaults |
| `MemoryRecord` | NO (do not modify) | Application-layer type; KMA types are separate contract-layer |
| `EvidenceArtifact` | NO (do not modify) | Application-layer type; KMA types are separate contract-layer |

## Type 1: KnowledgeObject

**JSON Schema**: `contracts/kma/KNOWLEDGE_OBJECT_SCHEMA_V1.json`
**Module**: `src/nexara_prime/models.py`
**Pydantic Model**: `KnowledgeObject(NModel)`

### Field Mapping

| JSON Schema Field | Python Type | Default | Required | Notes |
|-------------------|-------------|---------|----------|-------|
| `object_id` | `str` | — | YES | `new_id("kobj")` default via Field |
| `object_type` | `Literal["evidence", "memory", "receipt"]` | — | YES | |
| `mission_id` | `str \| None` | `None` | — | |
| `created_at` | `str` | `now_iso()` | YES | ISO-8601 UTC |
| `updated_at` | `str \| None` | `None` | — | |
| `sha256` | `str \| None` | `None` | — | Pattern: `^[a-f0-9]{64}$` |
| `envelope_sha256` | `str \| None` | `None` | — | Pattern: `^[a-f0-9]{64}$` |
| `idempotency_key` | `str \| None` | `None` | — | |
| `source_event_id` | `str \| None` | `None` | — | |
| `trace_id` | `str` | `""` | — | |
| `provenance` | `str` | `"runtime"` | — | Free string: runtime, human, import, migration, recovery |
| `status` | `str` | `"committed"` | — | 9-value enum concept |
| `superseded_by` | `str \| None` | `None` | — | |
| `confidence` | `float` | `1.0` | — | Range: 0.0-1.0 |
| `verified` | `bool` | `False` | — | |
| `canonical` | `bool` | `False` | — | |

### Serialization
- `model_dump(mode="json")` — Pydantic standard
- JSON serializable via existing SQLiteStore payload pattern

### Validation
- Pydantic `model_validate()` — field-level validation
- `Literal` type enforces `object_type` values
- Float range `confidence` validated by Pydantic `Field(ge=0.0, le=1.0)`

### ID Rules
- Default factory: `Field(default_factory=lambda: new_id("kobj"))`
- Stable: ID is generated once at creation, immutable

### Persistence
- Via `SQLiteStore.save_record(object_id, "knowledge_object", payload, created_at, mission_id)`
- `record_type = "knowledge_object"` — distinct from existing `memory`, `evidence`, `receipt` types

### API Boundary
- Public: `KnowledgeObject` is a contract-layer type
- `MemoryRecord` and `EvidenceArtifact` are application-layer types
- Conversion helpers may be added later (not Phase 2)

---

## Type 2: KnowledgeRelation

**JSON Schema**: `contracts/kma/KNOWLEDGE_RELATION_SCHEMA_V1.json`
**Module**: `src/nexara_prime/models.py`
**Pydantic Model**: `KnowledgeRelation(NModel)`

### Field Mapping

| JSON Schema Field | Python Type | Default | Required |
|-------------------|-------------|---------|----------|
| `relation_id` | `str` | `new_id("rel")` | YES |
| `source_id` | `str` | — | YES |
| `target_id` | `str` | — | YES |
| `relation_type` | `Literal["evidence_backing", "receipt_attests", "memory_derived_from", "supersedes", "conflicts_with", "references", "parent_of", "child_of", "depends_on", "produced_by", "verified_by"]` | — | YES |
| `mission_id` | `str \| None` | `None` | — |
| `created_at` | `str` | `now_iso()` | YES |
| `confidence` | `float` | `1.0` | — |
| `evidence_id` | `str \| None` | `None` | — |
| `bidirectional` | `bool` | `False` | — |
| `weight` | `float` | `1.0` | — |

### ID Rules
- Default factory: `Field(default_factory=lambda: new_id("rel"))`
- Uniqueness: `(source_id, target_id, relation_type)` is a natural key (not enforced at DB level in Phase 2)

### Persistence
- Via `SQLiteStore.save_record(relation_id, "knowledge_relation", payload, created_at, mission_id)`
- `record_type = "knowledge_relation"`

---

## Type 3: KnowledgeRecall

**JSON Schema**: `contracts/kma/KNOWLEDGE_RECALL_SCHEMA_V1.json`
**Module**: `src/nexara_prime/models.py`
**Pydantic Model**: `KnowledgeRecall(NModel)`

### Field Mapping

| JSON Schema Field | Python Type | Default | Required |
|-------------------|-------------|---------|----------|
| `query` | `str` | — | YES (min_length=1) |
| `layers` | `list[Literal["working", "episodic", "semantic", "procedural"]] \| None` | `None` | — |
| `top_k` | `int` | `10` | — (ge=1, le=100) |
| `mission_id` | `str \| None` | `None` | — |
| `min_confidence` | `float` | `0.3` | — (ge=0.0, le=1.0) |
| `include_candidates` | `bool` | `False` | — |
| `include_superseded` | `bool` | `False` | — |
| `trace_id` | `str` | `""` | — |

### Validation
- `query` min_length=1 via Pydantic `Field(min_length=1)`
- `top_k` range via `Field(ge=1, le=100)`
- `min_confidence` range via `Field(ge=0.0, le=1.0)`
- `layers` values validated by `Literal`

### Usage
- This is an INPUT type — consumed by `KnowledgeService.query()` or `MemoryLayerManager.search()`
- NOT persisted (ephemeral query object)
- NOT stored in SQLite

---

## Type 4: KnowledgeCommit

**JSON Schema**: `contracts/kma/KNOWLEDGE_COMMIT_SCHEMA_V1.json`
**Module**: `src/nexara_prime/models.py`
**Pydantic Model**: `KnowledgeCommit(NModel)`

### Field Mapping

| JSON Schema Field | Python Type | Default | Required |
|-------------------|-------------|---------|----------|
| `kind` | `MemoryKind` | — | YES (reuses existing enum) |
| `key` | `str` | — | YES (min_length=1) |
| `content` | `str` | — | YES (min_length=1) |
| `trace_id` | `str` | — | YES |
| `mission_id` | `str \| None` | `None` | — |
| `source_evidence_id` | `str \| None` | `None` | — |
| `idempotency_key` | `str \| None` | `None` | — (REQUIRED in Phase 2) |
| `confidence` | `float` | `1.0` | — (ge=0.0, le=1.0) |
| `receipt_id` | `str \| None` | `None` | — (Phase 2 addition) |
| `auto_commit` | `bool` | `False` | — |
| `provenance` | `str` | `"runtime"` | — |

### Validation
- `kind` validated by `MemoryKind` enum — identical 12 values to JSON Schema
- `key` and `content` min_length=1 via `Field(min_length=1)`
- `confidence` range via `Field(ge=0.0, le=1.0)`
- `idempotency_key` required in Phase 2 (validated at API boundary, not Pydantic level)

### Usage
- This is an INPUT type — consumed by `MemoryKernel.write()` or `MemoryKernel.propose()`
- NOT persisted directly (transformed to `MemoryRecord` by MemoryKernel)
- NOT stored in SQLite

---

## Type Relationship Diagram

```
KnowledgeCommit (input)
       │
       ▼
  MemoryKernel.write() ──→ MemoryRecord (application, persisted)
       │
       ▼
  KnowledgeObject (contract, may wrap MemoryRecord)

KnowledgeRecall (input)
       │
       ▼
  KnowledgeService.query() ──→ list[dict] (projection)
  MemoryLayerManager.search() ──→ list[{doc_id, content, score, ...}]

KnowledgeRelation (contract, persisted)
       │
       ▼
  SQLiteStore("knowledge_relation")
```

## Backward Compatibility

| Concern | Resolution |
|---------|------------|
| Existing `MemoryRecord` consumers | Unchanged — `MemoryRecord` is NOT modified |
| Existing `EvidenceArtifact` consumers | Unchanged — `EvidenceArtifact` is NOT modified |
| New `KnowledgeObject` vs existing types | Separate — no conflict, different names, different `record_type` |
| `MemoryKind` enum | Reused as-is — no new values, no changes |
| Schema evolution | `schema_version` field on each type — Phase 3 can add fields |

## Phase 2 Implementation Notes

1. Add 4 new model classes to `models.py` in the section after existing `MemoryRecord` definition
2. Use existing `NModel` base, `new_id()`, `now_iso()`, `Field` patterns
3. No changes to existing model classes
4. No new files — all in `models.py`
5. Test with `test_kma_types.py` validating JSON Schema ↔ Pydantic consistency

---

> Types frozen. Phase 2 implementation MUST conform to these mappings exactly.
