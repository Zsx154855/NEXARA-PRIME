# KMA Phase 1 Asset Inventory

> NEXARA Knowledge-Memory Authority — Read-Only Asset Census
> Generated: 2026-07-26
> Branch: work/nexara-knowledge-memory-authority-convergence-v1
> HEAD: e38aae49dc545162e3cc652e554ea26c0b8278e5
> Phase: 1 — Freeze Facts
> Status: CANONICAL

## Phase 0: Workspace Baseline

| Attribute | Value |
|-----------|-------|
| Git Root | `/Users/agentos/Worktrees/NEXARA-PRIME-kma-v1` |
| Branch | `work/nexara-knowledge-memory-authority-convergence-v1` |
| HEAD | `e38aae49dc545162e3cc652e554ea26c0b8278e5` |
| Git Status | CLEAN |
| Worktree | YES (linked from `/Users/agentos/NEXARA-PRIME/.git`) |
| Python | >=3.12, hatchling build, `nexara-prime` v0.1.0 |

## Phase 1A: Obsidian / Documentation Knowledge Graph

| Metric | Value |
|--------|-------|
| Total .md files | 55 |
| Directories with .md | 20 |
| Frontmatter coverage | 52/55 (94.5%) |
| Files without frontmatter | 3 (`WRITER_LEASE_AND_POLICY_GATES.md`, `NEXARA_12_PERSPECTIVE_STRATEGIC_ANALYSIS.md`, `13-Product-Reality/README.md`) |
| Wiki links | 48 |
| Markdown links | 0 |
| Broken links | 0 |
| README/INDEX coverage | All 20 directories have README or INDEX |
| Top linked pages | `00-INDEX.md`, `Product North Star`, `Knowledge Fabric Architecture`, `Runtime Truth`, `Source of Truth Policy`, `Three-Layer Model`, `UI Truth Contract`, `ADR README` |
| Status breakdown | canonical: ~40, review: ~3, draft: 0, deprecated: 0, superseded: 0, legacy: 0 |
| Canonical Source Map consistency | PARTIAL — maps reference some absolute paths not matching current worktree |

### Directory Distribution

| Directory | File Count |
|-----------|-----------|
| 02-Architecture/12-Layers/ | 13 |
| 06-ADRs/ | 8 |
| _templates/ | 5 |
| 04-Governance/ | 4 |
| 12-Operations/ | 3 |
| 01-Product/ | 1 |
| 02-Architecture/ | 2 |
| 03-Runtime/ | 2 |
| 05-UI-UX/ | 1 |
| 07-Missions/ | 1 |
| 08-Failure-Cases/ | 1 |
| 09-Evidence-Index/ | 1 |
| 10-Data-Contracts/ | 2 |
| 11-Evaluations/ | 1 |
| 13-Product-Reality/ | 1 |
| 99-Legacy/ | 1 |
| _generated/ | 1 |
| _inbox/ | 1 |
| maps/ | 2 |
| docs/ (root) | 4 |

### Reference Coverage

| Reference Type | Count |
|----------------|-------|
| Evidence references | Found across 04-Governance/Evidence Ledger Policy.md, 09-Evidence-Index/README.md |
| Receipt references | Found in WRITER_LEASE_AND_POLICY_GATES.md |
| Mission references | Found in 07-Missions/README.md |
| Capability references | Indirect in 02-Architecture/Three-Layer Model.md |
| Decision references | 7 ADRs in 06-ADRs/ |

## Phase 1B: Runtime Memory Census

| Attribute | Status |
|-----------|--------|
| MemoryKernel | IMPLEMENTED (634 lines) |
| MemoryLayerManager | IMPLEMENTED (635 lines total) |
| Architecture | 4-layer: Working, Episodic, Semantic, Procedural |
| Persistence | SQLite (via SQLiteStore, records table) |
| ID format | `memory_{uuid4().hex[:12]}` |
| Write entries | 11 methods (write, propose, commit_candidate, patch + layer-specific) |
| Read entries | 10 methods (inspect, candidates, layer-specific reads, search, stats) |
| Evidence association | YES — `source_evidence_id` + `evidence_refs` fields; enforced for DECISION/FAILURE/FAILURE_EXPERIENCE/PATCH types |
| Receipt association | NO — zero receipt references in memory.py |
| Mission association | YES — `mission_id` field on all operations |
| Idempotency | PARTIAL — only `patch()` has idempotency_key; `write()` and `propose()` generate fresh IDs each call |
| Conflict detection | YES — `propose()` detects same-key-different-content conflicts |
| Version support | NO — no content versioning; `schema_version` tracks model version only |
| Expiry support | NO — no TTL, GC, or retention; `clear_working_for_mission()` is manual only |
| Recovery | NO — no memory-specific recovery; cannot rebuild from evidence |
| Migration | PARTIAL — auto-migration on startup (ALTER TABLE), no formal versioned migrations |
| Status | **IMPLEMENTED** (with 9 known gaps) |

### Known Gaps

1. **CRITICAL**: No receipt association — audit trail incomplete
2. **HIGH**: `write()`/`propose()` not logically idempotent
3. **HIGH**: No expiry/retention for ephemeral memory
4. **MEDIUM**: No content versioning
5. **MEDIUM**: Patch reviews in-memory only, lost on restart
6. **MEDIUM**: `inspect()` returns unvalidated dicts
7. **LOW**: No formal migration system
8. **INFO**: Dual evidence fields (`source_evidence_id` + `evidence_refs`) with no relationship enforcement

## Phase 1C: Evidence / Receipt Census

### Evidence System

| Attribute | Status |
|-----------|--------|
| EvidenceStore | IMPLEMENTED (652 lines) |
| EvidenceArtifact model | IMPLEMENTED (~15 fields) |
| Hash verification | YES — sha256(content) + envelope_sha256 + integrity_sha256 (4-layer) |
| Idempotency | YES — via idempotency_key with replay/repair |
| SQLite persistence | YES — records table |
| JSON Schema | PARTIAL — `schemas/evidence_artifact.json` has only 7 fields, outdated vs Pydantic model |
| File-based evidence | 24 files in `.nexara/evidence/` (16 .md + 8 .json), NOT ingested into EvidenceStore |
| Legacy evidence | 8 EVIDENCE.json files in `reports/*/` directories, disconnected from main system |
| Status | **IMPLEMENTED** (with multi-store fragmentation) |

### Receipt System

| Attribute | Status |
|-----------|--------|
| Canonical Receipt model | MISSING — no single Pydantic model |
| Runtime receipt chain | IMPLEMENTED — `ToolInvocation.receipt_evidence_id` → `EvidenceArtifact.evidence_id`, verified by `verify_receipt_chain()` |
| Governance receipts | 9 JSON files in `.nexara/receipts/` with varying schemas |
| Operational receipts | `ConnectorReceipt` (connectors/base.py) + `SandboxReceipt` (sandbox_v2.py) — not persisted |
| Legacy receipts | 9 RECEIPT.json files in `reports/*/` directories |
| Hash verification | PARTIAL — some have evidence_sha256, others use git SHA |
| Status | **PARTIAL** — no canonical model, 4 separate receipt forms |

### Multiple Store Fragmentation

- **Evidence**: 3 locations (SQLite, `.nexara/evidence/`, `reports/*/`) — unsynchronized
- **Receipt**: 4 forms (`.nexara/receipts/`, `ToolInvocation` links, operational dataclasses, `reports/*/`) — no single canonical store
- **End-to-end verifiable**: PARTIAL — runtime chain works; file-based chain does not

## Phase 1D: Capability / Model History Census

| Attribute | Status |
|-----------|--------|
| CapabilityRegistry | IMPLEMENTED (converged V1+V2, 238 lines) |
| ID format | `<type>.<name>` (type in {skill, tool, model, memory, policy}) |
| Model in code | 7 fields (capability_id, name, capability_type, description, risk_level, enabled, input_schema) |
| Model in contract | 18 fields — 11 ONLY_IN_CONTRACT (provider, output_schema, permission_level, external_effect, idempotency, timeout_ms, retry_policy, rollback, evidence_policy, health_status, model_requirements) |
| Agents (Persona) | 9: NEXARA, ATLAS, NYX, ORION, SOLACE, VERTEX, ECHO, LUMEN, KAIROS |
| Roles (RuntimeRole) | 8: ORCHESTRATOR, PLANNER, ANALYST, RESEARCHER, EXECUTOR, REVIEWER, AUDITOR, ARCHIVIST |
| Providers | 6: mock, deepseek-v4-flash, deepseek-v4-pro, openai_compatible, local, unavailable |
| Models | 5: mock-v1, deepseek-v4-flash, deepseek-v4-pro, gpt-4o-mini, local-model |
| Routing rules | YES — tier selection by complexity/risk/context_size/latency_target |
| Circuit breaker | YES — per-provider failure tracking with auto-reset |
| History tracking | Success/failure: EXISTS, Latency: EXISTS (running avg), Token: PARTIAL, Cost: PARTIAL, Retry: PARTIAL, Recovery: PARTIAL |
| Evaluation | EXISTS_IN_CODE (`EvaluationEngine`), but mission-level only, not capability-level |
| Status | **IMPLEMENTED** (with contract-model gap) |

## Phase 1E: Chief Brain Recall Census

| Component | Status |
|-----------|--------|
| ChiefBrainKernel | **PARTIAL** — class exists (214 lines) but completely disconnected from all production execution paths |
| Intent normalization | PARTIAL — keyword matching only |
| Context assembly | IMPLEMENTED — `real_context.py` (177 lines) |
| Contract generation | IMPLEMENTED — `contract_engine.py` (24 lines), `mission_compiler.py` (48 lines) |
| Planning | PARTIAL — Planner role exists but no dedicated Planner class |
| Recall / retrieval | IMPLEMENTED — `rag_pipeline.py` (691 lines), `KnowledgeService` (56 lines) |
| Memory access | IMPLEMENTED — delegates to `MemoryKernel` |
| Evidence validation | IMPLEMENTED — `EvidenceStore.verify()` + `verify_receipt_chain()` |
| Conflict detection | IMPLEMENTED — `MemoryKernel.propose()` |
| Supersession detection | **MISSING** — zero code for detecting newer-version-replaces-older |
| Token budget | IMPLEMENTED — `resource_budget.py` |
| Receipt generation | IMPLEMENTED — via `EvidenceStore` |

### Critical Gap

`ChiefBrainKernel.submit()` is NEVER called from `runtime.py`, `orchestration.py`, `api.py`, or `cli.py`. The kernel class exists in isolation, only exercised by test fixtures. `NexaraRuntime` directly creates/plans/approves/runs missions without any kernel admission gate. The enforceable contract defined in `.nexara/contracts/chief_brain_kernel_contract_v1.yaml` is not enforced at runtime.

## Phase 1F: Duplicate Systems and Authority Conflicts

| Concern | Finding |
|---------|---------|
| Multiple Memory Stores | NO — single `MemoryKernel` + `MemoryLayerManager` |
| Multiple Evidence Stores | NO — single `EvidenceStore` (but file-based evidence is separate) |
| Multiple Receipt Stores | YES — 4 separate forms, no canonical model |
| Multiple Capability Registries | YES — 2 instances of same class in `runtime.py` (`self.capabilities` + `_adaptive_capabilities_v2`) with separate state |
| Multiple Token Compilers | YES — 2 instances in `runtime.py` (`self.tokens` + `_adaptive_tokens_v2`) |
| Multiple Mission ID Rules | NO — single `new_id()` centralized |
| Multiple Canonical Sources | YES — deprecated `.nexara/PROJECT_STATE.json` exists alongside active `.nexara/PROGRAM_STATE.json`; `cli.py` STILL reads deprecated file |
| Doc vs Runtime Conflicts | YES — `docs/09-Evidence-Index/README.md` references hardcoded absolute paths |
| Legacy referenced by active | YES — `cli.py` reads deprecated PROJECT_STATE; `.legacy.bak` files in `.nexara/evidence/` |
| Same object different IDs | NO — unified `new_id()` |
| **Duplicate System Count** | **3** |
| **Authority Conflict Count** | **3** |

## Summary

| System | Status | Lines | Files | Gaps |
|--------|--------|-------|-------|------|
| Knowledge Docs | IMPLEMENTED | — | 55 .md | 3 without frontmatter |
| Runtime Memory | IMPLEMENTED | 634 | 1 | 9 issues |
| Evidence | IMPLEMENTED | 652 | 1 | Multi-store fragmentation |
| Receipt | PARTIAL | — | 0 (no model) | No canonical model |
| Capability Registry | IMPLEMENTED | 238 | 2 (1 deprecated) | 11 contract-only fields |
| Chief Brain | PARTIAL | 214 | 1 | Not wired to runtime |
| Duplicate Systems | — | — | — | 3 duplicates + 3 conflicts |

*All findings are evidence-backed. No speculation. UNKNOWN where not verifiable.*
