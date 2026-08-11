# NEXARA Core v1.0 — Architecture Inventory

**Generated**: 2026-08-08T08:00:00Z  
**HEAD**: `8a75910`  
**Reference**: `.nexara/freeze/CURRENT_TRUTH.json`

---

## Core Object 1: Mission

| Attribute | Value |
|---|---|
| **Owner** | `models.py` → `Mission` (Pydantic BaseModel) |
| **Schema** | `mission_id`, `spec` (MissionSpec), `state` (MissionState), `contract` (WorkContract?), `plan` (MissionPlan?), `assignments` (list[AgentAssignment]), `pending_approval_id`, `paused`, `safe_mode`, `rollback_point`, `trace_id`, `result` (dict), `created_at`, `updated_at`, + Adaptive fields (`adaptive_mode`, `triage_result`, `scheduling_plan`, `routing_decisions`, `resource_budget`, `budget_usage`, `escalation_history`, `agent_lifecycle`) |
| **Lifecycle** | INTENT → CONTEXT → CONTRACT → PLAN → SIMULATION → APPROVAL → EXECUTION → VERIFICATION → EVIDENCE → MEMORY_PATCH → EVALUATION → COMPLETED (or BLOCKED/FAILED/ROLLED_BACK) |
| **Storage** | `SQLiteStore.save_record()` / `get_record()` — keyed by `mission_id` |
| **Interface** | `NexaraRuntime.create_mission()`, `get_mission()`, `run_mission()`, `inspect_mission()`, `pause()`, `resume()`, `rollback()`, `takeover()` |
| **Dependencies** | MissionSpec, WorkContract, MissionPlan, AgentAssignment, MissionState, MissionStateMachine |

---

## Core Object 2: MissionSpec (Task Definition)

| Attribute | Value |
|---|---|
| **Owner** | `models.py` → `MissionSpec` |
| **Schema** | `mission_id`, `title`, `objective`, `boundaries`, `constraints`, `deliverables`, `risks`, `acceptance_criteria`, `risk_level` (R0-R4), `source_dir`, `created_at`, `schema_version` |
| **Lifecycle** | Created by `MissionCompiler.compile()` → immutable after creation |
| **Storage** | Embedded in Mission record |
| **Interface** | `MissionCompiler.compile(objective, source_dir)` |
| **Dependencies** | RiskLevel enum |

---

## Core Object 3: WorkContract

| Attribute | Value |
|---|---|
| **Owner** | `models.py` → `WorkContract` |
| **Schema** | `contract_id`, `mission_id`, `version`, `status` (draft/approved), `objective`, `boundaries`, `constraints`, `deliverables`, `acceptance_criteria`, `risk_level`, `change_log`, `approved_at` |
| **Lifecycle** | draft (ContractEngine.create) → approved (ContractEngine.approve) |
| **Storage** | Embedded in Mission record, referenced by `mission.contract` |
| **Interface** | `ContractEngine.create(spec)`, `ContractEngine.approve(contract)` |
| **Dependencies** | MissionSpec |

---

## Core Object 4: MissionState (State Machine)

| Attribute | Value |
|---|---|
| **Owner** | `models.py` → `MissionState` (Enum, 33 values) |
| **Schema** | 15 original states (INTENT→COMPLETED/BLOCKED/FAILED/ROLLED_BACK) + 15 adaptive states (CREATED→CANCELLED/ROLLING_BACK) |
| **Lifecycle** | Governed by `MissionStateMachine.transition()` — `TRANSITIONS` matrix defines all legal moves |
| **Storage** | `mission.state` field (string), persisted via `_save_mission()` |
| **Interface** | `MissionStateMachine.can_transition(current, target)`, `.transition(mission, target, actor)` |
| **Dependencies** | EventBus, EvidenceStore |
| **Invariants** | No self-transitions, no state regression on resume, adaptive states reject in non-adaptive path |

---

## Core Object 5: Runtime Context (NexaraRuntime)

| Attribute | Value |
|---|---|
| **Owner** | `runtime.py` → `NexaraRuntime` |
| **Schema** | Composes: SQLiteStore, EventBus, SecurityAuditLedger, EvidenceStore, MemoryKernel, PolicyEngine, ApprovalEngine, WriterLeaseManager, CapabilityRegistry, AdaptiveScheduler, MissionCompiler, ContractEngine, TokenCompiler, ModelGateway, ToolRuntime, EvaluationEngine, MissionStateMachine, DurableRecovery, RealRepositoryContext |
| **Lifecycle** | `__init__()` → `create_mission()` → `plan_mission()` → `approve_mission()` → `run_mission()` (5-stage pipeline) |
| **Storage** | SQLite database (`nexara.db` / `hardening_acceptance.db`) |
| **Interface** | 30+ methods: mission CRUD, approval, execution pipeline, inspection, recovery, adaptive status |
| **Dependencies** | ALL core objects |

---

## Core Object 6: Capability

| Attribute | Value |
|---|---|
| **Owner** | `capabilities.py` → `CapabilityRegistry` |
| **Schema** | `Capability`: `capability_id`, `name`, `capability_type` (SKILL/TOOL/MODEL/MEMORY/POLICY), `description`, `risk_level`, `enabled`, `input_schema` |
| **Lifecycle** | Registered → enabled/disabled → used by tools/scheduler |
| **Storage** | `CapabilityRegistry` in-memory + `CapabilityHistory` in SQLite |
| **Interface** | `CapabilityRegistry.register()`, `.list()`, `.get()` |
| **Dependencies** | CapabilityType, RiskLevel, CapabilityHistory |

---

## Core Object 7: Evidence

| Attribute | Value |
|---|---|
| **Owner** | `evidence.py` → `EvidenceStore` |
| **Schema** | `EvidenceArtifact`: `evidence_id`, `mission_id`, `kind`, `title`, `content`, `sha256`, `actor`, `timestamp`, `verification_status`, `parent_evidence`, `idempotency_key` |
| **Lifecycle** | Added (unverified) → verified → referenced by memory/receipt |
| **Storage** | SQLite via `store.save_record()` with envelope integrity |
| **Interface** | `EvidenceStore.add()`, `.list()`, `.verify()`, `.verify_all()`, `.receipt_status()`, `.find_by_idempotency()` |
| **Dependencies** | SQLiteStore, EventBus, sha256 |
| **Invariants** | Evidence verified via `.verify()` before relying on stored content; idempotency_key prevents duplicates |

---

## Core Object 8: Memory

| Attribute | Value |
|---|---|
| **Owner** | `memory.py` → `MemoryKernel` |
| **Schema** | `MemoryRecord`: `memory_id`, `mission_id`, `kind` (MemoryKind enum: 14 types), `key`, `content`, `source_evidence_id`, `idempotency_key`, `supersedes`, `superseded_by`, `confidence`, `status`, `verified`, `canonical` |
| **Lifecycle** | Created → committed → potentially superseded |
| **Storage** | SQLite via `store.save_record()` |
| **Interface** | `MemoryKernel.patch()`, `.recall()`, `.list()`, `MemoryLayerManager` for layered recall |
| **Dependencies** | SQLiteStore, EventBus, EvidenceStore |
| **Invariants** | Every memory patch must be evidence-bound (`source_evidence_id` required) |

---

## Core Object 9: Knowledge

| Attribute | Value |
|---|---|
| **Owner** | `knowledge.py` + `models.py` → `KnowledgeObject`, `KnowledgeRelation`, `KnowledgeRecall`, `KnowledgeCommit` |
| **Schema** | `KnowledgeObject`: `object_id`, `object_type` (evidence/memory/receipt), `sha256`, `envelope_sha256`, `status` (committed→superseded), `confidence`; `KnowledgeRelation`: `source_id` → `target_id` with 11 relation types |
| **Lifecycle** | Committed → verified → potentially superseded |
| **Storage** | SQLite (same store) |
| **Interface** | `KnowledgeEngine.recall()`, `.commit()`, `.relate()` |
| **Dependencies** | SQLiteStore, MemoryKernel, EvidenceStore |

---

## Core Object 10: Approval

| Attribute | Value |
|---|---|
| **Owner** | `governance.py` → `ApprovalEngine` |
| **Schema** | `ApprovalRequest`: `approval_id`, `mission_id`, `action`, `risk_level`, `rationale`, `impact`, `status` (PENDING→APPROVED/REJECTED/CHANGES_REQUESTED/PAUSED/EXPIRED/CONSUMED), `decided_by`, `decision_note`, `proposal_sha256`, `expires_at` |
| **Lifecycle** | Requested (PENDING) → Decided (APPROVED/REJECTED/etc.) → Consumed (single_action) or Expired |
| **Storage** | SQLite with envelope integrity + event sourcing |
| **Interface** | `ApprovalEngine.request()`, `.decide()`, `.get()`, `.list()`, `.consume_single_action()` |
| **Dependencies** | SQLiteStore, EventBus, ApprovalStatus, RiskLevel |
| **Invariants** | All transitions validated via event sourcing integrity; consumed approvals cannot be reused |

---

## Core Object 11: Checkpoint (Recovery)

| Attribute | Value |
|---|---|
| **Owner** | `recovery.py` → `DurableRecovery` |
| **Schema** | Checkpoint data embedded in mission result dict; `RecoveryItem` with `recovery_id`, `mission_id`, `failure_class`, `root_cause`, `state` (PENDING→EXHAUSTED/ROLLED_BACK) |
| **Lifecycle** | Checkpoint created → recovery analyzed → strategy applied → exhausted/rolled_back |
| **Storage** | SQLite + mission.result dict |
| **Interface** | `DurableRecovery.checkpoint()`, `.recover()` |
| **Dependencies** | SQLiteStore, EventBus, Mission |

---

## Runtime Pipeline (5-Stage)

```
EXECUTION → VERIFICATION → EVIDENCE → MEMORY_PATCH → EVALUATION → COMPLETED
```

| Stage | Method | Responsibility |
|---|---|---|
| Execution | `_execute_stage()` | Model completion, tool invocation, report writing (WriterLease) |
| Verification | `_verify_stage()` | Report SHA-256 verification, IndependentReview reviewer verdict |
| Evidence | `_commit_evidence_stage()` | Execution result evidence, IndependentReview auditor verdict |
| Memory Patch | `_update_memory_stage()` | Evidence-bound memory patch |
| Evaluation | `_evaluate_stage()` | 6-dim evaluation (correctness, reliability, safety, evidence_coverage, token_efficiency, cost_score) |

## Invariants (from AGENTS.md)

1. No silent MockProvider fallback
2. No raw store.find_record bypass
3. No self-transitions
4. No state regression on resume
5. No duplicate side effects (idempotency_key)
6. Approval integrity (starts as "integrity_error")
7. Evidence integrity (verify before rely)
8. Provider unavailable is resumable
9. Adaptive states rejected in non-adaptive path
10. SDK compatibility inline in inspect_mission

---

**End of Architecture Inventory**  
*Reference: `.nexara/freeze/CURRENT_TRUTH.json`*
