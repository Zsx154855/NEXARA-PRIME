# G1 — First-Party Agent Identity Domain

**Gate:** G1 — 第一方 Agent Identity Domain
**Status:** PASS
**Date:** 2026-07-15

## Exit Criteria Assessment

| Criterion | Status | Detail |
|-----------|--------|--------|
| AgentIdentity | ✅ FROZEN | `agent_id=nexara_prime.agent`, `display_name=NEXARA`, `version=1.0.0` |
| Profile | ✅ FROZEN | 10 product principles, 24 capabilities in capability_profile |
| Memory Namespace | ✅ FROZEN | `nexara_prime.agent.memory` |
| 权限模板 | ✅ FROZEN | `AGENT_DEFAULT_PERMISSIONS` (10 permissions, 5 admin/secret denied) |
| Hermes runtime dependency=0 | ✅ VERIFIED | 0 `Persona.HERMES`, 0 `actor="hermes"`, 0 `import hermes` |

## Changes

### Persona.HERMES → Persona.NEXARA (BLOCKER-001 resolved)
- `src/nexara_prime/models.py:111` — enum member renamed
- `src/nexara_prime/scheduler.py:8` — default persona mapping
- `src/nexara_prime/adaptive_scheduler.py:21,250,293` — all 3 references
- `src/nexara_prime/runtime.py:179` — actor string literal
- `tests/test_core.py:61` — assertion updated
- `tests/test_hardening.py:418` — assertion updated

### AgentIdentity Model (new)
- `src/nexara_prime/identity.py` — `AgentIdentity` dataclass with 10 principles, 24 capabilities
- `src/nexara_prime/identity.py` — `AGENT_DEFAULT_PERMISSIONS` set (10 permissions)
- `src/nexara_prime/agent/__init__.py` — package entry point

### Test Added
- `tests/test_p0_repairs.py` — `test_agent_identity_first_party_defaults` — validates agent_id, display_name, principles (incl. Hermes dependency=0), denied permissions

## Verification

- 508/508 tests passing
- 0 Persona.HERMES references in src/
- 0 actor="hermes" references in src/
- 0 `import hermes` in product runtime
- AgentIdentity importable and defaults validated
