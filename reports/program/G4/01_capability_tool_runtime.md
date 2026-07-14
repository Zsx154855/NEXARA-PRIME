# G4 — Capability & Tool Runtime

**Gate:** G4 — Capability & Tool Runtime
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: 统一能力注册、健康、依赖、沙箱、幂等、连接器与模型路由

### Capability & Tool Runtime Surface

| Component | Module | Status | Tests |
|-----------|--------|--------|-------|
| Capability Registry V2 | `capability_registry_v2.py` | ✅ Running | — |
| Connector Registry | `connectors/registry.py` | ✅ Running | — |
| Provider Connector | `connectors/provider_connector.py` | ✅ Running | — |
| Connector Lifecycle | `connectors/lifecycle.py` | ✅ Running | — |
| Connector Health | `connectors/health.py` | ✅ Running | — |
| Sandbox V2 | `sandbox_v2.py` | ✅ Running | — |
| Tool Runtime | `tools.py` | ✅ Running | — |
| Model Router | `model_router.py` + CircuitBreaker | ✅ Running | — |
| Model Gateway | `model_gateway.py` + secret redaction | ✅ Running | — |
| Network Policy | `network_policy.py` | ✅ Running | — |

### Key Properties Verified

| Property | Implementation |
|----------|---------------|
| Unified registry | `CapabilityRegistryV2` — register, resolve, health, dependencies, score |
| Idempotency | `idempotency_key` on tool invocations; event idempotency (event_id + aggregate_id + event_type uniqueness) |
| Sandbox | `sandbox_v2.py` — tool execution isolation |
| Connector model | 8 connector modules: base, audit, browser_readonly, health, http_readonly, lifecycle, permissions, provider_connector, registry |
| Model routing | `ModelRouter` with CircuitBreaker, ProviderInfo, tiered routing (fast/reasoning/local) |
| Secret safety | `model_gateway.py` redacts secrets before persistence/telemetry |

### Test Baseline

120 G4-relevant tests passing. 508/508 full regression.
