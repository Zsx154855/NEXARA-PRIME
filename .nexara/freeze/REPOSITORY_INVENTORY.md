# NEXARA Core v1.0 — Repository Inventory

**Generated**: 2026-08-08T08:00:00Z  
**HEAD**: `8a75910` (`feat/brand-baihan`)  
**Source**: `src/nexara_prime/` (144 .py files) + `tests/` (98 .py files)  
**Governance**: NSEC V2.1 (19 chapters, 55 articles)

---

## 1. Core Kernel (`src/nexara_prime/`)

### 1.1 Runtime & Lifecycle

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `runtime.py` | 1105 | `NexaraRuntime` | Application service — coordinates kernel, 5-stage pipeline (execute→verify→evidence→memory→eval), adaptive runtime, adapters | models, state_machine, governance, evidence, memory, evaluation, tools, recovery, db, events | **ACTIVE** |
| `__init__.py` | 7 | Package | Exports SoulKernel, version 0.1.0 | soul | **ACTIVE** |
| `soul.py` | ~100 | `SoulKernel` | Constitutional identity verification, soul integrity | models | **ACTIVE** |
| `identity.py` | ~80 | Identity | Runtime identity fingerprint, owner binding | models, config | **ACTIVE** |

### 1.2 Data Models (Single Source of Truth)

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `models.py` | 909 | Data Models | **ALL** canonical Pydantic models: Mission, MissionSpec, WorkContract, MissionPlan, AgentAssignment, EvidenceArtifact, ApprovalRequest, WriterLease, ToolInvocation, MemoryRecord, KnowledgeObject, EvaluationResult, Capability + 30+ Adaptive Runtime models | pydantic, uuid, datetime | **FROZEN CANDIDATE** |
| `state_machine.py` | 71 | `MissionStateMachine` | Legal state transition matrix (original + adaptive), escalation/de-escalation validation | models, events, evidence | **FROZEN CANDIDATE** |

### 1.3 Governance

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `governance.py` | 500 | `PolicyEngine`, `ApprovalEngine`, `WriterLeaseManager` | Risk policy, human approval workflow, single-writer lease, integrity-validated transitions | models, db, events | **FROZEN CANDIDATE** |
| `kernel_boundary.py` | ~60 | Boundary | Kernel security boundary enforcement | models, governance | **ACTIVE** |
| `network_policy.py` | ~60 | Network Policy | Network access control rules | models, governance | **ACTIVE** |
| `policy_service.py` | ~80 | Policy Service | Dynamic policy evaluation service | models, governance | **ACTIVE** |
| `security_audit.py` | ~120 | `SecurityAuditLedger` | Deterministic security audit trail | db, models | **ACTIVE** |

### 1.4 Evidence & Memory

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `evidence.py` | ~200 | `EvidenceStore` | Idempotent evidence with envelope integrity, SHA-256, receipt tracking | db, events, models | **FROZEN CANDIDATE** |
| `memory.py` | ~250 | `MemoryKernel`, `MemoryLayerManager` | Evidence-bound memory patches, layer management, conflict resolution | db, events, evidence, models | **FROZEN CANDIDATE** |
| `knowledge.py` | ~150 | Knowledge | Knowledge graph operations, recall, commit | db, models | **ACTIVE** |

### 1.5 Execution

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `tools.py` | ~350 | `ToolRuntime` | Governed tool invocation (file_read, file_write_report, code_exec, etc.), sandbox, policy check | db, events, evidence, governance, models | **FROZEN CANDIDATE** |
| `evaluation.py` | ~180 | `EvaluationEngine` | 6-dim idempotent mission evaluation (correctness, reliability, safety, evidence_coverage, token_efficiency, cost_score) | db, events, models | **FROZEN CANDIDATE** |
| `mission_compiler.py` | ~150 | `MissionCompiler` | Compile human intent → MissionSpec | models | **ACTIVE** |
| `mission_triage.py` | ~120 | `MissionTriageEngine` | Triage missions by complexity, risk, cost | models | **ACTIVE** |
| `contract_engine.py` | 23 | `ContractEngine` | Work contract creation/approval | models | **ACTIVE** |
| `token_compiler.py` | ~120 | `TokenCompiler` | Prompt token compilation for model calls | models | **ACTIVE** |
| `token_compiler_v2.py` | ~80 | `TokenCompilerV2` | V2 enhanced token compilation | models | **ACTIVE** |
| `real_context.py` | ~100 | `RealRepositoryContext`, `RepositoryContext` | Real git/file context collection with deterministic hashing | git | **ACTIVE** |

### 1.6 Model Gateway

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `model_gateway.py` | ~200 | `ModelGateway`, `MockProvider`, `OpenAICompatibleProvider`, `UnavailableProvider`, `LocalModelProvider` | Provider abstraction, mock/unavailable safety, no-silent-fallback invariant | models, config | **FROZEN CANDIDATE** |
| `model_router.py` | ~120 | `ModelRouter`, `CircuitBreaker` | Adaptive model routing with circuit breaker | models | **ACTIVE** |

### 1.7 CLI & API

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `cli.py` | 615 | CLI | Mission create/status/plan/approve/run, adaptive commands | runtime, models, config | **ACTIVE** |
| `api.py` | 235 | FastAPI | REST API — inspect_mission, SDK compatibility | runtime, models | **ACTIVE** |

### 1.8 Infrastructure

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `db.py` | 1294 | `SQLiteStore` | SQLite persistence, envelope integrity, event sourcing, record CRUD | sqlite3 | **FROZEN CANDIDATE** |
| `events.py` | ~80 | `EventBus` | Event sourcing bus, publish/subscribe | db | **FROZEN CANDIDATE** |
| `config.py` | 38 | `Settings` | Environment/config loading, model provider, mock_model | pydantic, os | **ACTIVE** |
| `recovery.py` | ~120 | `DurableRecovery` | Checkpoint/idempotency, mission recovery | db, events, models | **FROZEN CANDIDATE** |
| `capabilities.py` | 491 | `CapabilityRegistry` | Tool/skill/model capability registration | models | **FROZEN CANDIDATE** |
| `capability_registry_v2.py` | 10 | `CapabilityRegistryV2` | V2 capability registry (thin) | capabilities | **DEPRECATED CANDIDATE** |
| `scheduler.py` | ~250 | `AdaptiveScheduler` | Mission agent assignment scheduling | capabilities, models | **ACTIVE** |
| `adaptive_runtime.py` | 280 | `AdaptiveRuntime` | Adaptive mission orchestration | models, scheduler, etc. | **ACTIVE** |
| `adaptive_scheduler.py` | 501 | `AdaptiveMultiAgentScheduler` | Multi-agent adaptive scheduling with ROI analysis | models | **ACTIVE** |
| `orchestration.py` | ~500 | `RuntimeOrchestrator` | Autonomous runtime orchestration control plane | db, events, evidence, models | **ACTIVE** |
| `repair_loop.py` | ~80 | `RepairLoop` | Automated repair loop with evidence | evidence, governance | **ACTIVE** |
| `program_loop.py` | ~200 | `ProgramLoop` | Continuous program loop execution | store, events, evidence, runtime | **ACTIVE** |
| `independent_review.py` | ~100 | `IndependentReview` | Reviewer/auditor verdict generation | models | **ACTIVE** |
| `escalation.py` | ~100 | `EscalationEngine` | Adaptive mode escalation/de-escalation | models | **ACTIVE** |
| `resource_budget.py` | ~120 | `ResourceBudgetManager` | Token/cost/time budget enforcement | models | **ACTIVE** |
| `telemetry.py` | ~100 | Telemetry | Runtime telemetry collection | models, db | **ACTIVE** |
| `benchmark_runner.py` | 126 | Benchmark | Adaptive benchmark running and comparison | models | **ACTIVE** |

### 1.9 Governed Adapters

| File | Lines | Owner | Responsibility | Dependencies | Status |
|---|---|---|---|---|---|
| `browser_adapter.py` | 348 | `GovernedBrowserAdapter`, `MockBrowserDriver` | Governed browser automation with evidence | evidence, governance | **ACTIVE** |
| `computer_use_adapter.py` | 269 | `GovernedComputerUseAdapter`, `MockComputerUseDriver` | Governed computer use with evidence | evidence, governance | **ACTIVE** |
| `git_adapter.py` | ~80 | `GovernedGitAdapter`, `MockGitDriver` | Governed git operations with evidence | evidence, governance | **ACTIVE** |
| `message_adapter.py` | ~80 | `GovernedMessageAdapter`, `MockMessageProvider` | Governed messaging with evidence | evidence, governance | **ACTIVE** |
| `deployment_adapter.py` | ~80 | `GovernedDeploymentAdapter`, `MockDeploymentDriver` | Governed deployment with evidence | evidence, governance | **ACTIVE** |
| `rag_pipeline.py` | ~80 | `RAGPipeline`, `MockEmbedder` | RAG pipeline for memory layer | models | **ACTIVE** |

---

## 2. Brain Subpackage (`src/nexara_prime/brain/`) — 35 files

### 2.1 Core Brain

| File | Responsibility | Status |
|---|---|---|
| `kernel.py` | ChiefBrainKernel — sole Mission Admission Boundary | **ACTIVE** |
| `__init__.py` | Brain package (133 lines — substantial init) | **ACTIVE** |
| `chief_brain_kernel.py` | Top-level CBK (294 lines) — delegates to brain/kernel | **POTENTIAL DUPLICATE** |

### 2.2 Brain Sub-modules

| File | Responsibility | Status |
|---|---|---|
| `mission_intelligence_engine.py` (611L) | Mission intelligence analysis | **ACTIVE** |
| `memory_controller.py` (415L) | Memory layer orchestration | **ACTIVE** |
| `agent_orchestrator.py` (344L) | Agent orchestration within brain | **ACTIVE** |
| `reasoning/kernel.py` (324L) | Reasoning kernel | **ACTIVE** |
| `runtime/persistent_runtime.py` (307L) | Persistent runtime state | **ACTIVE** |
| `evolution_engine.py` (307L) | Evolution pipeline | **ACTIVE** |
| `knowledge_graph.py` (293L) | Knowledge graph operations | **ACTIVE** |
| `mission_compiler.py` (285L) | Brain-level mission compilation | **POTENTIAL DUPLICATE** (see top-level mission_compiler.py) |
| `db.py` (249L) | Brain-level database | **POTENTIAL DUPLICATE** (see top-level db.py 1294L) |
| `capability_registry.py` (247L) | Brain-level capability registry | **POTENTIAL DUPLICATE** (see top-level capabilities.py 491L) |
| `evolution/boundary.py` (230L) | Evolution boundary | **ACTIVE** |
| `long_term_memory.py` (190L) | Long-term memory | **ACTIVE** |
| `planning_engine.py` (156L) | Planning | **ACTIVE** |
| `experience_recall.py` (151L) | Experience recall | **ACTIVE** |
| `reasoning/context_assembler.py` (152L) | Context assembly | **ACTIVE** |
| `reasoning/self_check.py` (148L) | Self-check | **ACTIVE** |
| `evaluation_engine.py` (147L) | Brain-level evaluation | **POTENTIAL DUPLICATE** (see top-level evaluation.py) |
| `mission_intelligence.py` (142L) | Mission intelligence | **ACTIVE** |
| `experience_store.py` (140L) | Experience store | **ACTIVE** |
| `experience_learner.py` (139L) | Experience learner | **ACTIVE** |
| `self_reflection_engine.py` (139L) | Self-reflection | **ACTIVE** |
| `world_model.py` (123L) | World model | **ACTIVE** |
| `decision_engine.py` (122L) | Decision engine | **ACTIVE** |
| `preference_model.py` (119L) | Preference model | **ACTIVE** |
| `mission_manager_v3.py` (120L) | Mission manager V3 | **ACTIVE** |
| `deep_reasoning.py` (107L) | Deep reasoning | **ACTIVE** |
| `reasoning_budget.py` (107L) | Reasoning budget | **ACTIVE** |
| `meta_cognition.py` (99L) | Metacognition | **ACTIVE** |
| `mission_types.py` (91L) | Mission type definitions | **ACTIVE** |
| `research_intelligence.py` (95L) | Research intelligence | **ACTIVE** |
| `cognitive_models.py` (92L) | Cognitive models | **ACTIVE** |
| `model_policy.py` (90L) | Model policy | **ACTIVE** |
| `strategic_planning.py` (88L) | Strategic planning | **ACTIVE** |
| `environment/intelligence.py` (86L) | Environment intelligence | **ACTIVE** |
| `brain_receipt.py` (77L) | Brain receipt | **ACTIVE** |
| `decay_config.py` (68L) | Decay configuration | **ACTIVE** |
| `provenance.py` (64L) | Provenance tracking | **ACTIVE** |
| `consolidation_rules.py` (58L) | Consolidation rules | **ACTIVE** |
| `goal_manager.py` (54L) | Goal manager | **ACTIVE** |
| `context_engine.py` (39L) | Context engine | **ACTIVE** |
| `planner.py` (41L) | Planner | **ACTIVE** |
| `agent_identity/registry.py` (89L) | Agent identity registry | **ACTIVE** |
| `scheduler/autonomous_scheduler.py` (105L) | Autonomous scheduler | **ACTIVE** |
| `governance/autonomous_governance.py` (384L) | Autonomous governance | **ACTIVE** |
| `reasoning/` (7 files) | Reasoning subsystem | **ACTIVE** |

---

## 3. Council Subpackage (`src/nexara_prime/council/`) — 16 files

| File | Responsibility | Status |
|---|---|---|
| `__init__.py` (254L) | Council package — substantial init | **ACTIVE** |
| `pipeline.py` (520L) | Council pipeline execution | **ACTIVE** |
| `mission_dna.py` (282L) | Mission DNA encoding | **ACTIVE** |
| `adapters/base.py` (172L) | Adapter base class | **ACTIVE** |
| `adapters/schemas.py` (183L) | Adapter schemas | **ACTIVE** |
| `adapters/deepseek_adapter.py` (105L) | DeepSeek adapter | **ACTIVE** |
| `adapters/openai_adapter.py` (105L) | OpenAI adapter | **ACTIVE** |
| `adapters/anthropic_adapter.py` (108L) | Anthropic adapter | **ACTIVE** |
| `adapters/hermes_adapter.py` (120L) | Hermes adapter | **ACTIVE** |
| `adapters/codex_cli_adapter.py` (125L) | Codex CLI adapter | **ACTIVE** |
| `adapters/xai_adapter.py` (104L) | xAI adapter | **ACTIVE** |
| `adapters/redaction.py` (102L) | Redaction | **ACTIVE** |
| `adapters/registry.py` (76L) | Adapter registry | **ACTIVE** |
| `runtime/conflict_resolver.py` (161L) | Conflict resolution | **ACTIVE** |
| `runtime/mission_router.py` (160L) | Mission routing | **ACTIVE** |
| `runtime/token_governor.py` (175L) | Token governance | **ACTIVE** |
| `governance/approval_policy.yaml` | Approval policy config | **ACTIVE** |
| `governance/risk_policy.yaml` | Risk policy config | **ACTIVE** |

---

## 4. Connectors (`src/nexara_prime/connectors/`) — 9 files

| File | Responsibility | Status |
|---|---|---|
| `base.py` (190L) | Base connector | **ACTIVE** |
| `browser_readonly.py` (223L) | Read-only browser connector | **ACTIVE** |
| `http_readonly.py` (86L) | Read-only HTTP connector | **ACTIVE** |
| `registry.py` (67L) | Connector registry | **ACTIVE** |
| `health.py` (65L) | Health checks | **ACTIVE** |
| `provider_connector.py` (58L) | Provider connector | **ACTIVE** |
| `audit.py` (50L) | Audit connector | **ACTIVE** |
| `permissions.py` (39L) | Permissions | **ACTIVE** |
| `lifecycle.py` (24L) | Lifecycle hooks | **ACTIVE** |

---

## 5. Secrets (`src/nexara_prime/secrets/`) — 5 files

| File | Responsibility | Status |
|---|---|---|
| `base.py` | Base secret store | **ACTIVE** |
| `env.py` | Environment variable secrets | **ACTIVE** |
| `keychain.py` | macOS Keychain integration | **ACTIVE** |
| `memory.py` | In-memory secrets (testing) | **ACTIVE** |

---

## 6. Product Reality (`src/nexara_prime/product_reality/`) — 4 files

| File | Responsibility | Status |
|---|---|---|
| `models.py` | Product reality models | **ACTIVE** |
| `genome.py` | Product genome | **ACTIVE** |
| `evolution.py` | Product evolution | **ACTIVE** |
| `twin.py` | Digital twin | **ACTIVE** |

---

## 7. Other Subpackages

| Package | Files | Responsibility | Status |
|---|---|---|---|
| `delivery_controller/` | 2 | Delivery migration control | **ACTIVE** |
| `agent/` | 1 | Agent package init | **ACTIVE** |
| `platform/` | 1 | Platform package init | **ACTIVE** |

---

## 8. Test Suite (`tests/`) — 98 files, 2044 tests

| Category | Count | Key Files |
|---|---|---|
| Brain tests | ~20 | `test_kernel.py` (603L), `test_decision_engine.py` (475L), `test_memory_brain.py` (184L) |
| Council tests | ~3 | `test_council_v2.py` (753L) |
| Reasoning tests | ~7 | `test_kernel.py`, `test_confidence.py`, etc. |
| Runtime tests | ~10 | `test_adaptive_runtime.py` (1535L), `test_runtime_v2_codex_regression.py` (474L) |
| Governance tests | ~3 | `test_nsec_governance.py` (625L) |
| KMA tests | ~7 | `test_kma_*.py` — memory/knowledge authority |
| Product reality | ~3 | `test_product_reality_v2_full_audit.py` (2153L) |
| Security | ~3 | `test_security_hardening.py` (751L) |
| Orchestration | ~1 | `test_orchestration.py` (1026L) |
| Other | ~41 | Core, CI, SDK, program loop, etc. |

---

## 9. Governance Documents

| File | Responsibility | Status |
|---|---|---|
| `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md` (547L) | **Supreme Governance** — 19 chapters, 55 articles | **FROZEN** |
| `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md` (364L) | Superseded V1 | **SUPERSEDED** |
| `authority_index.yaml` (175L) | Authority index | **ACTIVE** |
| `nsec.yaml` (71L) | NSEC machine-readable config | **ACTIVE** |
| `contracts/MERGE_CONTRACT_V1.yaml` (166L) | Merge contract | **ACTIVE** |
| `releases/RELEASE_FLOW_V1.md` (215L) | Release flow | **ACTIVE** |
| `releases/RELEASE_APPROVAL_MATRIX_V1.yaml` (188L) | Release approval matrix | **ACTIVE** |
| `recovery/ROLLBACK_POLICY_V1.md` (230L) | Rollback policy | **ACTIVE** |
| `baselines/v0.1.0/` (7 files) | v0.1.0 baseline artifacts | **FROZEN** |

---

## 10. Identified Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | `chief_brain_kernel.py` (top-level) vs `brain/kernel.py` — potential duplicate ChiefBrainKernel | DUPLICATE | MEDIUM |
| 2 | `brain/mission_compiler.py` vs top-level `mission_compiler.py` — two compilers | DUPLICATE | MEDIUM |
| 3 | `brain/db.py` (249L) vs top-level `db.py` (1294L) — two DB layers | DUPLICATE | HIGH |
| 4 | `brain/capability_registry.py` (247L) vs top-level `capabilities.py` (491L) | DUPLICATE | MEDIUM |
| 5 | `brain/evaluation_engine.py` vs top-level `evaluation.py` | DUPLICATE | MEDIUM |
| 6 | `capability_registry_v2.py` — 10 lines, thin wrapper | DEPRECATED | LOW |
| 7 | 3 deprecated `.nexara/` files still present | LEGACY | LOW |
| 8 | `Persona.HERMES` string constant — naming only, not runtime | NAMING | LOW |
| 9 | `brain/__init__.py` is 133 lines — should be thin | STRUCTURE | LOW |

---

**End of Repository Inventory**  
*Reference: `.nexara/freeze/CURRENT_TRUTH.json`*
