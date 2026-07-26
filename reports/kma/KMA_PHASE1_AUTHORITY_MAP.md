# KMA Phase 1 Authority Map

> NEXARA Knowledge-Memory Authority — Canonical Authority Boundaries
> Generated: 2026-07-26
> Phase: 1 — Freeze Authority
> Status: CANONICAL

## Authority Hierarchy

The following defines the single canonical authority for each domain object, derived from real code, contracts, and governance documents at HEAD `e38aae4`.

```
NSEC V2.1 (SUPREME)
  └── Governance Contracts (.nexara/contracts/)
        ├── Authority Matrix V1 (authority_matrix_v1.yaml)
        ├── Canonical Domain Model V1 (canonical_domain_model_v1.yaml)
        ├── Chief Brain Kernel Contract V1 (chief_brain_kernel_contract_v1.yaml)
        ├── Memory Knowledge Contract V1 (memory_knowledge_contract_v1.yaml)
        ├── Capability Registry Contract V1 (capability_registry_contract_v1.yaml)
        └── Tool Runtime Contract V1 (tool_runtime_contract_v1.yaml)
              └── Runtime Implementation (src/nexara_prime/)
                    ├── Evidence (evidence.py) — append-only, immutable
                    ├── Memory (memory.py) — evidence-backed, approved patches
                    ├── Capabilities (capabilities.py) — converged V1+V2
                    ├── Chief Brain (chief_brain_kernel.py) — admission boundary
                    └── Knowledge Service (knowledge.py) — read-only query
                          └── Obsidian Docs (docs/) — human-readable surface
                                └── Search Index — derived, rebuildable
```

## Single Authority Per Domain

| Domain | Canonical Authority | Location | Backup/Shadow | Notes |
|--------|-------------------|----------|---------------|-------|
| Mission State | `NexaraRuntime` | `runtime.py` | — | Single owner of mission lifecycle |
| State Transitions | `MissionStateMachine` | `state_machine.py` | — | All transitions validated here |
| Evidence | `EvidenceStore` | `evidence.py` | `.nexara/evidence/` (human surface) | SQLite is canonical; file-based is human-readable |
| Receipt | `ToolInvocation.receipt_evidence_id` | `models.py` | `.nexara/receipts/` (governance surface) | No canonical Pydantic model yet |
| Memory | `MemoryKernel` | `memory.py` | — | Single write authority |
| Knowledge Query | `KnowledgeService` | `knowledge.py` | `RAGPipeline` (search layer) | Read-only; wraps MemoryKernel |
| Capability Registry | `CapabilityRegistry` | `capabilities.py` | `capability_registry_v2.py` (deprecated alias) | V1+V2 converged; 2 instances bug |
| Model Routing | `ModelRouter` | `model_router.py` | — | Single routing authority |
| Model Gateway | `ModelGateway` | `model_gateway.py` | — | Single provider abstraction |
| Governance | `PolicyEngine` + `ApprovalEngine` | `governance.py` | `policy_service.py` (not wired) | Single approval authority |
| Admission | `ChiefBrainKernel` | `chief_brain_kernel.py` | — | NOT WIRED (deferred G2-D) |
| Human Docs | Obsidian Vault | `docs/` | — | Git-backed; not runtime authority |

## Prohibited Paths

| Path | Why Prohibited |
|------|---------------|
| Obsidian → Mission State | Docs cannot change runtime state |
| Search Index → Memory Write | Derived index cannot become fact source |
| UI → Runtime Metric | Canvas cannot bypass Runtime (INVARIANT_02) |
| Executor → Self-Verify | Kernel MUST NOT self-verify (PROHIBIT_01) |
| Agent → Permission Grant | Permissions always external (PROHIBIT_03) |
| Any → Evidence Overwrite | Evidence is append-only (PROHIBIT_04) |

## Phase 2 Writer Scope

Phase 2 may ONLY modify these files (the KMA implementation surface):

- `src/nexara_prime/chief_brain_kernel.py` — wire into runtime
- `src/nexara_prime/runtime.py` — integrate kernel admission
- `src/nexara_prime/memory.py` — add idempotency, receipt link, expiry
- `src/nexara_prime/evidence.py` — add ingestion bridge
- `src/nexara_prime/models.py` — add Receipt model, MemoryRecord fields
- `src/nexara_prime/knowledge.py` — add supersession detection
- `src/nexara_prime/capabilities.py` — add contract fields
- `src/nexara_prime/cli.py` — fix PROJECT_STATE → PROGRAM_STATE
- `contracts/kma/` — KMA Contract V1 (NEW)
- `schemas/` — update evidence_artifact.json, add new schemas
- `tests/` — new KMA tests
- `reports/kma/` — Phase 2 reports
- `evidence/kma/` — Phase 2 evidence

Phase 2 MUST NOT modify:

- `.nexara/contracts/` — frozen at G1, read-only
- `.nexara/evidence/` — immutable
- `.nexara/receipts/` — immutable
- `docs/` — Obsidian vault preserved
- `governance/` — NSEC supreme
- `experience/` — UI layer
- `platform/` — SDK
- `scripts/` — operational scripts
- Any file not explicitly in allowed scope

## Authority Validation

- [x] Single Memory Store: `MemoryKernel` in `memory.py` — NO DUPLICATE
- [x] Single Evidence Store: `EvidenceStore` in `evidence.py` — NO DUPLICATE
- [x] Single Capability Registry: `CapabilityRegistry` in `capabilities.py` — 2 INSTANCES BUG
- [x] Single Mission ID: `new_id()` in `models.py` — NO DUPLICATE
- [x] Governance layers consistent with runtime
- [x] Obsidian is human-readable surface (confirmed)
- [x] Search Index is derived (confirmed)

*All claims verified against actual code at HEAD e38aae4.*
