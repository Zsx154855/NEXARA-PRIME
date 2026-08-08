# NEXARA Core v1.0 — Dependency Audit

**Generated**: 2026-08-08T08:00:00Z | **HEAD**: `8a75910`

---

## 1. Object Dependency Graph

```
Mission ─────────────────────────────────────────────────────────────┐
  ├── MissionSpec (has-a, immutable)                                  │
  ├── WorkContract (has-a, draft→approved)                            │
  ├── MissionPlan (has-a, steps with AgentAssignments)                │
  ├── AgentAssignment (has-many, role+persona+capabilities)           │
  ├── MissionState (state field, governed by MissionStateMachine)     │
  └── result dict (checkpoints, model tokens, evidence refs)          │
                                                                      │
NexaraRuntime (composes ALL) ────────────────────────────────────────┤
  ├── SQLiteStore ──► db.py (1294L)                                   │
  ├── EventBus ──► events.py                                         │
  ├── SecurityAuditLedger ──► security_audit.py                       │
  ├── EvidenceStore ──► evidence.py ──► SQLiteStore + EventBus        │
  ├── MemoryKernel ──► memory.py ──► SQLiteStore + EventBus + Evidence│
  ├── PolicyEngine ──► governance.py                                  │
  ├── ApprovalEngine ──► governance.py ──► SQLiteStore + EventBus     │
  ├── WriterLeaseManager ──► governance.py ──► SQLiteStore + EventBus │
  ├── CapabilityRegistry ──► capabilities.py                          │
  ├── AdaptiveScheduler ──► scheduler.py ──► CapabilityRegistry       │
  ├── MissionCompiler ──► mission_compiler.py ──► models              │
  ├── ContractEngine ──► contract_engine.py ──► models                │
  ├── TokenCompiler ──► token_compiler.py ──► models                  │
  ├── ModelGateway ──► model_gateway.py ──► config + provider impls   │
  ├── ToolRuntime ──► tools.py ──► store+events+evidence+policy       │
  ├── EvaluationEngine ──► evaluation.py ──► store+events             │
  ├── MissionStateMachine ──► state_machine.py ──► events+evidence    │
  ├── DurableRecovery ──► recovery.py ──► store+events                │
  └── RealRepositoryContext ──► real_context.py ──► git/filesystem    │
```

## 2. Module Dependency Graph (simplified)

```
                    ┌──────────┐
                    │ models.py │  (909L — ALL canonical types)
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────────┐
        ▼                ▼                     ▼
   ┌─────────┐    ┌────────────┐      ┌──────────────┐
   │  db.py  │    │ governance │      │state_machine │
   │(1294L)  │    │   (500L)   │      │   (71L)      │
   └────┬────┘    └─────┬──────┘      └──────┬───────┘
        │               │                    │
   ┌────┴────┐    ┌─────┴──────┐      ┌──────┴───────┐
   │ events  │    │ evidence   │      │   runtime    │
   │         │    │ memory     │      │  (1105L)     │
   └─────────┘    │ evaluation │      │ composes all │
                  │ tools      │      └──────────────┘
                  │ recovery   │
                  └────────────┘
```

**Dependency Flow**: `models → db → events → evidence/memory/governance → tools/evaluation → runtime`

## 3. Runtime Call Graph (5-Stage Pipeline)

```
create_mission()
  → MissionCompiler.compile()
  → store.save_record()
  → events.publish("mission.created")
  → evidence.add("mission_spec")

plan_mission()
  → state_machine.transition(INTENT→CONTEXT)
  → tools.invoke("file_read") [context collection]
  → contract_engine.create()
  → scheduler.schedule()
  → plan generation
  → policy.requires_approval(R2)
  → APPROVAL gate (human)

run_mission()
  → dispatch[mission.state]
  
  _execute_stage():
    → tokens.compile()
    → models.complete() [ModelGateway]
    → tools.invoke("code_exec") [sandbox check]
    → tools.invoke("file_write_report") [WriterLease]
    → state_machine.transition(→VERIFICATION)
    
  _verify_stage():
    → _verify_report() [SHA-256]
    → IndependentReview.reviewer_verdict()
    → evidence.add("verification_report")
    → state_machine.transition(→EVIDENCE)
    
  _commit_evidence_stage():
    → evidence.add("execution_result")
    → IndependentReview.auditor_verdict()
    → state_machine.transition(→MEMORY_PATCH)
    
  _update_memory_stage():
    → memory.patch("mission.completed_report")
    → state_machine.transition(→EVALUATION)
    
  _evaluate_stage():
    → evaluator.evaluate() [6-dim]
    → _completion_gate()
    → state_machine.transition(→COMPLETED/BLOCKED)
```

## 4. Capability Dependency Graph

```
CapabilityRegistry (capabilities.py, 491L)
  ├── SKILL capabilities
  ├── TOOL capabilities
  │   ├── file_read → tools.py
  │   ├── file_write_report → tools.py
  │   ├── code_exec → tools.py
  │   ├── browser_readonly → browser_adapter.py
  │   └── computer_use → computer_use_adapter.py
  ├── MODEL capabilities
  │   ├── deepseek → council/adapters/deepseek_adapter.py
  │   ├── openai → council/adapters/openai_adapter.py
  │   ├── anthropic → council/adapters/anthropic_adapter.py
  │   └── local → model_gateway.py (LocalModelProvider)
  ├── MEMORY capabilities
  │   └── memory_kernel → memory.py
  └── POLICY capabilities
      └── policy_engine → governance.py
```

---

## 5. Identified Issues

### 5.1 Circular Dependencies
- **NONE detected** — dependency flow is strictly `models → db → events → * → runtime`

### 5.2 Duplicate Responsibilities (HIGH priority)

| # | Duplicate | Evidence | Risk |
|---|---|---|---|
| D1 | **Two DB layers**: `db.py` (1294L top-level) vs `brain/db.py` (249L) | Both import sqlite3, both have store semantics | Data inconsistency, two truth sources |
| D2 | **Two ChiefBrainKernels**: `chief_brain_kernel.py` (294L top-level) vs `brain/kernel.py` (171L) | Both named ChiefBrainKernel, different implementations | Conflicting Mission Admission Boundaries |
| D3 | **Two MissionCompilers**: `mission_compiler.py` (top-level) vs `brain/mission_compiler.py` (285L) | Both compile human intent → MissionSpec | Divergent compilation semantics |
| D4 | **Two CapabilityRegistries**: `capabilities.py` (491L) vs `brain/capability_registry.py` (247L) | Both register capabilities | Capability inconsistency |
| D5 | **Two EvaluationEngines**: `evaluation.py` (top-level) vs `brain/evaluation_engine.py` (147L) | Both perform 6-dim evaluation | Divergent evaluation criteria |

### 5.3 Hidden Interfaces
- `runtime.py:_ensure_adapters()` — lazy-initializes 7 adapters via global module-level variables — not discoverable via public API
- `runtime.py:_ensure_adaptive_imports()` — lazy-initializes 7 adaptive components via global module-level variables
- `brain/__init__.py` is 133 lines — substantially more than a package init should be

### 5.4 Cross-Layer Calls
- `runtime.py` directly imports from `brain/`, `council/`, `connectors/` — expected for composition root
- `brain/kernel.py` imports from top-level `models`, `db` — clean
- No bottom-up calls detected (lower layers don't import runtime)

---

## 6. Dependency Health Summary

| Metric | Status |
|---|---|
| Circular dependencies | **CLEAN** — 0 detected |
| Duplicate responsibilities | **5 ISSUES** — see D1-D5 above |
| Hidden interfaces | **2 ISSUES** — lazy adapter init |
| Cross-layer violations | **CLEAN** — dependency direction respected |
| Dead code | `capability_registry_v2.py` (10L thin wrapper) |

---

**End of Dependency Audit**
