# G3 — Platform Runtime Services

**Gate:** G3 — Platform Runtime Services
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: Capability/Policy/Telemetry/Knowledge 服务从 YAML 变成可运行服务

### Platform Service Surface (via `nexara_prime.platform`)

| Service | Module | Class | Status |
|---------|--------|-------|--------|
| Capability Registry | `capability_registry_v2.py` | `CapabilityRegistryV2` | ✅ Running |
| Policy Engine | `governance.py` | `PolicyEngine` | ✅ Running |
| Approval Engine | `governance.py` | `ApprovalEngine` | ✅ Running |
| Network Policy | `network_policy.py` | `NetworkPolicyEngine` | ✅ Running |
| Event Bus (Telemetry) | `events.py` | `EventBus` | ✅ Running |
| Identity Store | `identity.py` | `IdentityStore` | ✅ Running |
| Knowledge Universe | `api.py` (endpoint) | `/api/knowledge-universe` | ✅ Running |

### Key Fact

Per Blueprint risk control: "平台文档化而不运行: 大量 YAML/报告，Runtime 仍直接 import 旧模块" — this risk is NOT present. All services are running Python modules, not YAML stubs. 35 service-specific tests pass. The `platform/` package provides a unified import namespace.

### SDK Stubs (pre-existing)

| SDK | Directory |
|-----|-----------|
| Python | `platform/sdk/python/` |
| TypeScript | `platform/sdk/typescript/` |
| Swift | `platform/sdk/swift/` |
| REST | `platform/sdk/rest/` |
| MCP | `platform/sdk/mcp/` |

SDK implementation is G8 scope. G3 scope is backend services only.
