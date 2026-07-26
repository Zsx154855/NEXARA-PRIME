# G3 Reality Mapping — Platform Runtime Services

**Date:** 2026-07-24
**Gate:** G3 (Platform Runtime Services)
**Status:** REALITY_MAPPING
**Evidence Head:** `d275065`
**Exit Condition:** "Capability/Policy/Telemetry/Knowledge 服务从 YAML 变成可运行服务"

---

## 1. Current State: What Already Exists

### Capability Services

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `capabilities.py` | 238 | RUNNABLE | CapabilityRegistry — discovery, validation, health checking |
| `capability_registry_v2.py` | 10 | STUB | Thin placeholder, imports from V1 |
| `tools.py` | ~600 | RUNNABLE | ToolRuntime — sandbox execution |
| `connectors/` | 9 modules | RUNNABLE | 9 connector types with registry, health, lifecycle |
| `sandbox_v2.py` | ~430 | RUNNABLE | Sandbox V2 isolation |

**Gap:** CapabilityRegistry V2 is a thin stub. V1 is fully functional. G3 needs to promote V2 to full implementation.

### Policy Services

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `governance.py` | ~550 | RUNNABLE | PolicyEngine, ApprovalEngine, WriterLeaseManager |
| `network_policy.py` | ~190 | RUNNABLE | NetworkPolicyEngine |
| `escalation.py` | ~275 | RUNNABLE | EscalationEngine — policy-based escalation |
| `resource_budget.py` | ~290 | RUNNABLE | Resource budget enforcement |
| `security_audit.py` | ~165 | RUNNABLE | SecurityAuditLedger |

**Gap:** Policy services exist but are embedded in `NexaraRuntime` as direct dependencies. G3 needs to make them independently runnable services with their own lifecycle (start/stop/health).

### Telemetry Services

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `aos/health_monitor.pyc` | N/A | COMPILED ONLY | Health monitor — no source file found |
| `events.py` | ~52 | RUNNABLE | EventBus — pub/sub for runtime events |
| `connectors/health.py` | ~49 | RUNNABLE | CircuitBreaker, ConnectorHealthMonitor |
| `connectors/audit.py` | ~30 | RUNNABLE | ConnectorAuditTrail |

**Gap:** No dedicated telemetry module. Health monitoring is fragmented across connectors and compiled bytecode. G3 needs a unified TelemetryService.

### Knowledge Services

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `memory.py` (MemoryKernel) | ~680 | RUNNABLE | Memory management with 4-layer architecture |
| `rag_pipeline.py` | ~600 | RUNNABLE | Retrieval-augmented generation |
| `real_context.py` | ~180 | RUNNABLE | RealRepositoryContext |
| Reports: `G5/01_memory_knowledge_fabric.md` | N/A | DOCUMENT | Knowledge fabric design doc |
| Reports: `knowledge_validation.json` | N/A | DATA | Validation data |

**Gap:** Knowledge services are split between Memory (storage/retrieval) and RAG (augmentation). No unified KnowledgeService. G5's knowledge fabric is documented but not implemented.

---

## 2. G3 Scope: What Needs to Become Runnable

| Service | Current | G3 Target |
|---------|---------|-----------|
| CapabilityRegistry V2 | STUB (10 lines) | Full implementation with V1→V2 migration |
| PolicyService | Embedded in governance.py | Standalone runnable service with health endpoint |
| TelemetryService | Fragmented | Unified service: metrics, health, audit aggregation |
| KnowledgeService | Split across memory + RAG | Unified service: query, retrieval, fabric integration |

---

## 3. G3 Implementation Strategy

### Phase A: Capability Registry V2
- Promote `capability_registry_v2.py` from stub to full implementation
- Implement V2 registration, discovery, health, dependency resolution
- Backward compatible with V1

### Phase B: Policy Service
- Extract PolicyEngine + ApprovalEngine into runnable PolicyService
- Add health check, metrics, configuration reload
- Service lifecycle: start → health → policy evaluation → stop

### Phase C: Telemetry Service
- Create unified `telemetry.py` service
- Aggregate: EventBus events, ConnectorHealthMonitor, CircuitBreaker, AuditTrail
- Export: metrics endpoint, health dashboard data

### Phase D: Knowledge Service
- Create unified `knowledge.py` service
- Integrate: MemoryKernel queries, RAG pipeline, RepositoryContext
- Knowledge fabric: query interface for agent knowledge retrieval

---

## 4. Files to Create (NO existing code modified)

```
src/nexara_prime/capability_registry_v2.py  (expand stub → full)
src/nexara_prime/policy_service.py          (NEW — extract from governance)
src/nexara_prime/telemetry.py               (NEW — unified telemetry)
src/nexara_prime/knowledge.py               (NEW — unified knowledge service)
tests/test_g3_capability.py                 (NEW)
tests/test_g3_policy.py                     (NEW)
tests/test_g3_telemetry.py                  (NEW)
tests/test_g3_knowledge.py                  (NEW)
```

---

## 5. Constraints

- NO modification to runtime.py core logic
- NO modification to governance.py (policy service WRAPS, not replaces)
- NO modification to memory.py
- Services are OPT-IN wrappers, not mandatory replacements
- All existing tests must continue to pass
