# Capability Registry Convergence Report

## Pre-Convergence State

Two parallel capability registries co-existed:

| Module | Class | Role |
|--------|-------|------|
| `src/nexara_prime/capabilities.py` | `CapabilityRegistry` | V1: static registration, resolve, mount |
| `src/nexara_prime/capability_registry_v2.py` | `CapabilityRegistryV2` | V2: evidence-scored, decay, confidence-gating |

Three call sites:

| Caller | Line | Import |
|--------|------|--------|
| `runtime.py` | 213 | `from .capabilities import CapabilityRegistry` (primary) |
| `runtime.py` | 172 | `from .capability_registry_v2 import CapabilityRegistryV2` (adaptive, conditional) |
| `scheduler.py` | 3 | `from .capabilities import CapabilityRegistry` |
| `platform/__init__.py` | 19 | `from nexara_prime.capability_registry_v2 import CapabilityRegistryV2 as CapabilityRegistry` (alias re-export) |

## Convergence Decision

**Authoritative module**: `src/nexara_prime/capabilities.py :: CapabilityRegistry`

V2 features (update_score, list_capable, get_score, decay, confidence gating) merged INTO `CapabilityRegistry`.

`capability_registry_v2.py` reduced to thin compatibility alias re-exporting from `capabilities.py`. Marked as DEPRECATED — removal target v0.2.0.

## Register() API Compatibility

Single `register()` method accepts both calling conventions:
- V1: `register(Capability(...))` — object registration
- V2: `register("tool.read", name="Read File", supported_task_types=["executor"])` — scored registration

All 742 tests pass with unified API. No caller changes required.

## Verification

| Check | Result |
|-------|--------|
| Authoritative module count | 1 |
| Backwards compatibility | Maintained |
| Tests | 742/742 PASS |
| Import path preservation | All old imports still work |
