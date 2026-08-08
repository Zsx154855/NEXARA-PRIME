# NEXARA Core v1.0 — Core Contracts

**Generated**: 2026-08-08T08:00:00Z | **HEAD**: `8a75910`

---

## 1. Core Objects (`core_objects.md`)

### 1.1 Mission
- **File**: `src/nexara_prime/models.py:Mission`
- **Schema**: mission_id, spec (MissionSpec), state (MissionState), contract (WorkContract?), plan (MissionPlan?), assignments (list[AgentAssignment]), pending_approval_id, paused, safe_mode, rollback_point, trace_id, result (dict), created_at, updated_at + 7 adaptive fields
- **Lifecycle**: INTENT → CONTEXT → CONTRACT → PLAN → SIMULATION → APPROVAL → EXECUTION → VERIFICATION → EVIDENCE → MEMORY_PATCH → EVALUATION → COMPLETED | BLOCKED | FAILED | ROLLED_BACK
- **Storage**: SQLite, keyed by mission_id
- **Invariants**: No self-transitions, no state regression on resume, ProviderUnavailable is resumable not terminal

### 1.2 MissionSpec
- **File**: `src/nexara_prime/models.py:MissionSpec`
- **Schema**: mission_id, title, objective, boundaries, constraints, deliverables, risks, acceptance_criteria, risk_level (R0-R4), source_dir, created_at, schema_version
- **Lifecycle**: Created by MissionCompiler.compile() → immutable

### 1.3 WorkContract
- **File**: `src/nexara_prime/models.py:WorkContract`
- **Schema**: contract_id, mission_id, version, status (draft/approved), objective, boundaries, constraints, deliverables, acceptance_criteria, risk_level, change_log, approved_at
- **Lifecycle**: draft → approved

### 1.4 MissionState (33 values)
- **Original (15)**: Intent, Context, Contract, Plan, Simulation, Approval, Execution, Verification, Evidence, MemoryPatch, Evaluation, Completed, Blocked, Failed, RolledBack
- **Adaptive (15)**: Created, Triaged, Contracted, Planned, Scheduled, AwaitingApproval, Running, Verifying, Degraded, Paused, Cancelled, RollingBack
- **Terminal (3)**: Completed, Failed, RolledBack

### 1.5 MissionStateMachine
- **File**: `src/nexara_prime/state_machine.py:MissionStateMachine`
- **TRANSITIONS**: Dict[MissionState, Set[MissionState]] — complete legal transition matrix
- **Escalation**: S0→S1→S2→S3 (monotonic increase only)

---

## 2. Capability Registry (`capability_registry.md`)

### 2.1 CapabilityType (5 types)
- **SKILL** — Agent skills
- **TOOL** — Executable tools (file_read, file_write_report, code_exec, browser_readonly, computer_use)
- **MODEL** — Provider models (deepseek, openai, anthropic, local)
- **MEMORY** — Memory operations
- **POLICY** — Governance policies

### 2.2 CapabilityRegistry
- **File**: `src/nexara_prime/capabilities.py` (491L) — **SINGLE AUTHORITY**
- **Interface**: `.register()`, `.list()`, `.get()`
- **Invariant**: All tool invocations MUST route through `ToolRuntime.invoke()` → `CapabilityRegistry`

### 2.3 ToolRuntime
- **File**: `src/nexara_prime/tools.py`
- **Interface**: `.invoke(mission_id, tool_name, arguments, trace_id, ...)`
- **Error Model**: 32 FailureCode + 34 ReasonCode
- **Governance**: PolicyEngine check per invocation; WriterLease for file_write_report

---

## 3. Runtime Contract (`runtime_contract.md`)

### 3.1 NexaraRuntime
- **File**: `src/nexara_prime/runtime.py:NexaraRuntime` (1105L)
- **Composes**: SQLiteStore, EventBus, SecurityAuditLedger, EvidenceStore, MemoryKernel, PolicyEngine, ApprovalEngine, WriterLeaseManager, CapabilityRegistry, AdaptiveScheduler, MissionCompiler, ContractEngine, TokenCompiler, ModelGateway, ToolRuntime, EvaluationEngine, MissionStateMachine, DurableRecovery, RealRepositoryContext

### 3.2 5-Stage Pipeline
```
Execution → Verification → Evidence → MemoryPatch → Evaluation → Completed
```

### 3.3 10 Runtime Invariants
1. No silent MockProvider fallback — mock_model=true is only path
2. No raw store.find_record bypass — replay from mission.result
3. No self-transitions — stages advance forward only
4. No state regression — resume() only unpauses
5. No duplicate side effects — idempotency_key on all artifacts
6. Approval integrity — starts as "integrity_error", not silent "pending"
7. Evidence integrity — verify() before relying on stored content
8. Provider unavailable is resumable — stays in Execution, not terminal Failed
9. Adaptive states rejected — Running/Verifying/Degraded → ADAPTIVE_RECOVERY_REQUIRED
10. SDK compatibility inline — state, spec, title, objective, created_at in inspect_mission

### 3.4 ModelGateway
- **File**: `src/nexara_prime/model_gateway.py`
- **Providers**: MockProvider (mock_model=true only), OpenAICompatibleProvider, LocalModelProvider, UnavailableProvider
- **CircuitBreaker**: Shared via `_shared_breaker`

---

## 4. Bootstrap Spec (`bootstrap_spec.md`)

### 4.1 Settings
- **File**: `src/nexara_prime/config.py:Settings`
- **from_env()**: Loads NEXARA_MODEL_PROVIDER, NEXARA_MOCK_MODEL, DB path, workspace/report roots

### 4.2 Bootstrap Sequence
1. `Settings.from_env()` — load configuration
2. `Settings.ensure_dirs()` — create workspace/report directories
3. `SQLiteStore(db_path)` — initialize database with schema migration
4. `NexaraRuntime.__init__()` — compose all 19 services in deterministic order
5. `_build_model_gateway()` — select provider (mock/openai/deepseek/local/unavailable)
6. Ready — no business logic executed

### 4.3 Verifications
- Provider availability checked via `_build_model_gateway()`
- `_provider_unavailable` flag set if no valid provider configured
- `mock_model=true` is only path to MockProvider

---

## 5. Dependency Graph (`dependency_graph.md`)

```
models.py (909L)
  ├── db.py (1294L)
  │   └── events.py
  ├── governance.py (500L)
  │   └── [depends on: db, events, models]
  ├── state_machine.py (71L)
  │   └── [depends on: events, evidence, models]
  ├── evidence.py
  │   └── [depends on: db, events, models]
  ├── memory.py
  │   └── [depends on: db, events, evidence, models]
  ├── evaluation.py
  │   └── [depends on: db, events, models]
  ├── tools.py
  │   └── [depends on: db, events, evidence, governance, models]
  ├── capabilities.py (491L)
  │   └── [depends on: models]
  ├── recovery.py
  │   └── [depends on: db, events, models]
  ├── config.py (38L)
  ├── cli.py (615L)
  │   └── [depends on: runtime, models, config]
  ├── api.py (235L)
  │   └── [depends on: runtime, models]
  └── runtime.py (1105L)
      └── [composes ALL above]
```

Dependency direction: **models → db → events → services → runtime** (strict, no cycles)

---

## 6. CORE_VERSION.md

```yaml
version: "1.0.0"
status: "FROZEN"
frozen_at: "2026-08-08T08:00:00Z"
repository_sha: "8a75910c5f7e7d9c3c8d769307decbef4c74433b"
branch: "feat/brand-baihan"
tag: "v0.1.0"
previous_version: "0.1.0 (Engineering Baseline)"
gates: "7/7 PASS"
tests: "2044 passed, 0 failed"
governance: "NSEC V2.1"
evidence_root: ".nexara/freeze/"
```

---

**End of Core Contracts**
