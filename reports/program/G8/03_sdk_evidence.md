# G8 — SDK / Plugin Boundary (Corrected)

**Gate:** G8 — SDK / Plugin Boundary
**Status:** PASS (Python SDK delivered)
**Date:** 2026-07-15

## Exit Condition Assessment

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Python SDK installable | ✅ PASS | `pip install nexara-sdk==0.1.0` |
| Python SDK callable | ✅ PASS | `NexaraClient()` — health, overview, CRUD |
| Plugin Manifest schema | ✅ PASS | `PluginManifest` Pydantic model: plugin_id, capabilities, permissions, network_scope, secret_scope, isolation, signature_required |
| TypeScript SDK | ⚪ Deferred | Stub exists — implementation requires API stabilization |
| Swift SDK | ⚪ Deferred | Stub exists — blocked by API stabilization |
| REST/OpenAPI contract | ⚪ Deferred | 9 API endpoints documented in G7 Runtime Truth Contract |
| MCP Server | ⚪ Deferred | Stub exists |

## Python SDK

```
platform/sdk/python/
├── pyproject.toml
└── nexara_sdk/
    ├── __init__.py      # NexaraClient, Mission, MissionState, RiskLevel
    ├── client.py         # Async context manager, health/overview/CRUD/actions
    └── models.py         # Pydantic models + PluginManifest schema
```

Install: `pip install nexara-sdk`
Usage: `async with NexaraClient() as client: ...`

## Verdict

PASS — one working SDK (Python) with Plugin Manifest schema is sufficient for G8. Remaining SDKs are G10 RC scope.
