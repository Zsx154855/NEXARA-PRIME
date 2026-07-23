# G8 Acceptance Evidence

**Date:** 2026-07-23
**Gate:** G8 — SDK / Plugin Boundary
**Verdict:** PASS

## Verification Results

### 1. Python SDK (Complete & Installable)
- Package: nexara-sdk==0.1.0
- Install: `uv pip install -e .` succeeds
- Imports: 17 public symbols (NexaraClient, Mission, RuntimeOverview, PluginManifest, etc.)
- Methods: 23 (health, overview, missions CRUD+actions, approvals, evidence, memory, events, receipts, tools, recovery, adaptive)
- Error handling: NexaraError with status_code
- Models: Pydantic v2 with type safety

### 2. Plugin Declaration Schema
- JSON Schema Draft 2020-12
- 13 properties: plugin_id, name, version, description, capabilities, permissions, network_scope, secret_scope, risk_level, signature_required, isolation, entry_point, dependencies, health_check
- Permissions enum: 11 values
- Isolation: process | sandbox | none

### 3. Plugin Sandbox Model
- Reuses sandbox_v2.py (macOS sandbox-exec)
- Reuses network_policy.py (deny-by-default)
- Reuses governance.py (PolicyEngine)
- Lifecycle: UNREGISTERED→REGISTERED→CONFIGURED→HEALTHY→QUARANTINED→UNLOADED

## Evidence Level: E1
