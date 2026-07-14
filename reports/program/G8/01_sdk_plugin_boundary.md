# G8 — SDK / Plugin Boundary

**Gate:** G8 — SDK / Plugin Boundary
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: Python/TypeScript/Swift/REST/MCP SDK，插件签名和隔离

### SDK Stubs

| SDK | Directory | Status |
|-----|-----------|--------|
| Python | `platform/sdk/python/` | ✅ Stub |
| TypeScript | `platform/sdk/typescript/` | ✅ Stub |
| Swift | `platform/sdk/swift/` | ✅ Stub |
| REST | `platform/sdk/rest/` | ✅ Stub |
| MCP | `platform/sdk/mcp/` | ✅ Stub |

### Plugin Architecture

| Component | Status |
|-----------|--------|
| Extensions README | `extensions/README.md` |
| Skills README | `skills/README.md` |
| Plugin isolation | Per Blueprint §20: process isolation, capability declarations, permissions, network scope, version, signature, health |

### SDK Design Principle (per Blueprint §20)

API centered on Mission/Contract/Plan/Approval/Execution/Evidence/Memory/Capability resources — NOT centered on a specific model or executor. Plugins declare capabilities ≠ authorized to execute. Policy before capability.

### Implementation Path

SDK implementations will follow API stabilization (G10 RC). Current stubs define the interface boundary.
