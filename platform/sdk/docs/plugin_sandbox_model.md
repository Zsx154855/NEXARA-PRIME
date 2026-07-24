# NEXARA Plugin Sandbox Model

**Version:** 1.0
**Date:** 2026-07-23
**Applies to:** G8 Plugin Boundary

## Principle

> Plugin declaration != authorization. Capability declaration is necessary but not sufficient. Policy must grant permission separately. — Blueprint §19, NSEC V2.1 Article 42

## Isolation Levels

| Level | Name | Mechanism | Use Case |
|-------|------|-----------|----------|
| `none` | In-Process | Direct Python import | Development only; trusted internal plugins |
| `process` | Separate Process | subprocess + IPC (stdin/stdout JSON-RPC) | Default for R0-R2 plugins |
| `sandbox` | macOS Sandbox | `sandbox-exec` with custom profile | R3-R4 plugins, network-facing plugins |

## Plugin Lifecycle

```
UNREGISTERED → REGISTERED → CONFIGURED → HEALTHY → QUARANTINED → UNLOADED
                    │            │           │
                    ▼            ▼           ▼
                VALIDATION    STARTING    STOPPED
```

1. **Registration:** Plugin declares manifest.json. Manifest validated against schema.
2. **Validation:** Permission scope checked against PolicyEngine. Risk level assessed.
3. **Configuration:** Network scope, secret scope, isolation level applied.
4. **Startup:** Plugin loaded in configured isolation level.
5. **Health Check:** Periodic health verification. Unhealthy → QUARANTINED.
6. **Quarantine:** Failed health checks or policy violations → immediate isolation.
7. **Unload:** Graceful termination with cleanup.

## Security Bounds

### Process Isolation (default)
- Subprocess spawned via `subprocess.Popen`
- Communication via stdin/stdout JSON-RPC
- No shared memory
- Process killed on timeout or policy violation

### macOS Sandbox (sandbox level)
- Reuses `sandbox_v2.py` — the same sandbox-exec used for ToolRuntime
- Profile restricts: file system (read-only project dir), network (allowlist only), process (no spawn)
- Secret scope: only Keychain paths declared in manifest

### Secret Access
- Plugins reference secrets by path: `nexara/plugin/<plugin_id>/<key>`
- Secrets never passed in environment variables
- Secret access logged to EvidenceStore

## Signature Verification (Future)

When `signature_required: true`:
- Plugin must include `manifest.sig` (Ed25519 signature of manifest.json)
- Public key registered in NEXARA trust store
- Signature verified at registration time
- Unsigned plugins: REGISTRATION BLOCKED

## Implementation Map

| Component | Location |
|-----------|----------|
| Plugin Manifest Schema | `platform/sdk/schemas/plugin_manifest_v1.json` |
| Python SDK PluginManifest | `platform/sdk/python/nexara_sdk/models.py::PluginManifest` |
| Sandbox Runtime | `src/nexara_prime/sandbox_v2.py` (existing) |
| Network Policy | `src/nexara_prime/network_policy.py` (existing) |
| Policy Engine | `src/nexara_prime/governance.py::PolicyEngine` (existing) |
