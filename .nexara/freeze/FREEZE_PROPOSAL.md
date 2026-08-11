# NEXARA Core v1.0 — Freeze Proposal

**Generated**: 2026-08-08T08:00:00Z | **HEAD**: `8a75910`

---

## Frozen (Immutable After Seal)

### 1. Core Object Model
- **Mission** — `models.py:Mission` — mission_id, spec, state, contract, plan, assignments, result, trace_id
- **MissionSpec** — `models.py:MissionSpec` — title, objective, boundaries, risk_level, acceptance_criteria
- **WorkContract** — `models.py:WorkContract` — contract_id, status (draft→approved), version, change_log
- **MissionState** — `models.py:MissionState` — 33 states, 15 original + 15 adaptive + 3 terminal
- **MissionStateMachine** — `state_machine.py:MissionStateMachine` — TRANSITIONS matrix, can_transition/transition
- **MissionPlan** — `models.py:MissionPlan` — plan_id, steps (PlanStep with role+persona+capabilities)
- **AgentAssignment** — `models.py:AgentAssignment` — assignment_id, persona, runtime_role, capabilities
- **EvidenceArtifact** — `models.py:EvidenceArtifact` — evidence_id, sha256, envelope integrity
- **MemoryRecord** — `models.py:MemoryRecord` — memory_id, kind (14 types), source_evidence_id
- **ApprovalRequest** — `models.py:ApprovalRequest` — approval_id, status lifecycle, integrity validation
- **EvaluationResult** — `models.py:EvaluationResult` — 6-dim scoring (correctness, reliability, safety, etc.)
- **ToolInvocation** — `models.py:ToolInvocation` — invocation_id, failure_code (32), reason_code (34)
- **Capability** — `models.py:Capability` — capability_id, type (5 types), risk_level

### 2. Capability Schema
- **CapabilityType**: SKILL, TOOL, MODEL, MEMORY, POLICY
- **ToolRegistry**: file_read, file_write_report, code_exec, browser_readonly, computer_use
- **CapabilityRegistry**: `capabilities.py` (491L) — single authority for capability registration
- **CapabilityHistory**: per-invocation tracking with provider/model/success/tokens

### 3. Runtime Contract
- **NexaraRuntime** — composition of 19 services; 5-stage pipeline (execute→verify→evidence→memory→eval)
- **ModelGateway** — provider abstraction; NO silent MockProvider fallback
- **ToolRuntime** — governed invocation; policy check per invocation; WriterLease for writes
- **10 Runtime Invariants** — documented in AGENTS.md, verified by 2044 tests

### 4. Bootstrap Contract
- **Settings** — `config.py` — from_env, model_provider, mock_model
- **NexaraRuntime.__init__()** — composes all services in deterministic order
- **Store initialization** — SQLiteStore with schema migration
- **No business logic in bootstrap** — all logic in runtime methods

---

## Flexible (May Evolve Post-Freeze)

### 1. UI & Theme
- **LivingInterface/** — SwiftUI macOS app; SkinEngine with 5 themes
- **ui/** — Next.js 16 dashboard; Tailwind v4; shadcn/ui
- **App icon catalog** — 24 icons in 3 boards

### 2. Adapters
- **Provider adapters**: deepseek, openai, anthropic, hermes, codex, xai — pluggable
- **Governed adapters**: browser, computer_use, git, messenger, deployment — pluggable
- **Connector registry**: browser_readonly, http_readonly — extensible

### 3. Plugins
- **Skills system** — 100+ skills registered
- **MCP servers** — browser-use, genui, schedule
- **Qoder plugins** — extensible

---

## Freeze Boundary

```
═══════════════════════════════════════════════════════
                    FROZEN ZONE
═══════════════════════════════════════════════════════
  models.py          — ALL canonical types
  state_machine.py   — ALL legal transitions
  governance.py      — ApprovalEngine, PolicyEngine
  evidence.py        — EvidenceStore
  memory.py          — MemoryKernel
  evaluation.py      — EvaluationEngine
  tools.py           — ToolRuntime
  capabilities.py    — CapabilityRegistry
  recovery.py        — DurableRecovery
  runtime.py         — NexaraRuntime (5-stage pipeline)
  db.py              — SQLiteStore
  events.py          — EventBus
  config.py          — Settings
  soul.py            — SoulKernel
  cli.py             — CLI interface
  api.py             — REST API interface
═══════════════════════════════════════════════════════
                    FLEXIBLE ZONE
═══════════════════════════════════════════════════════
  LivingInterface/   — macOS app, themes, icons
  ui/                — Web dashboard
  brain/             — Cognitive modules (after merge)
  council/           — Multi-provider adapters
  connectors/        — External connectors
  secrets/           — Secret backends
  product_reality/   — Product genome
  skills/            — Skills system
  extensions/        — Extensions
═══════════════════════════════════════════════════════
```

---

## Freeze Preconditions (from ARCHITECTURE_AUDIT)

| # | Precondition | Status |
|---|---|---|
| F1 | Single DB authority (merge brain/db.py → db.py) | **BLOCKING** |
| F2 | Single ChiefBrainKernel (merge chief_brain_kernel.py → brain/kernel.py) | **BLOCKING** |
| F3 | Remove dead code (capability_registry_v2.py) | Non-blocking |
| F4 | Remove deprecated .nexara files | Non-blocking |

### Freeze Decision: CONDITIONAL PASS

The architecture is **freezable** — all 11 Core Objects have clear single owners at the top level. Two blocking duplicates (D1: DB, D2: CBK) exist in the `brain/` subpackage but do not affect the core frozen zone. The freeze can proceed with the following note:

> **Freeze Note F1-F2**: `brain/db.py` and `chief_brain_kernel.py` are recognized as duplicates of frozen core modules. They MUST be merged into their canonical counterparts before v1.0.0 release. Until merged, the top-level modules (`db.py`, `brain/kernel.py`) are the authoritative frozen sources per NSEC Art.30 (Single Source of Truth).

---

**End of Freeze Proposal**
