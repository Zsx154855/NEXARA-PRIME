# G0 — Product Boundary Freeze: Scope & Boundaries

**Gate:** G0 — 产品宪章与边界冻结
**Status:** PASS
**Date:** 2026-07-15

## 1. 唯一事实源 (Single Source of Truth) — FROZEN

| Layer | Source | Status |
|-------|--------|--------|
| Program authority | `NEXARA_PROGRAM_CONSTITUTION_V1.md` | FROZEN |
| Architecture | `NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md` | FROZEN |
| Gate DAG | `NEXARA_DEVELOPMENT_GATES_V1.yaml` | FROZEN |
| Runtime state | `.nexara/PROGRAM_STATE.json` | ACTIVE |
| Gate progress | `.nexara/GATE_STATUS.json` | ACTIVE |
| Project facts | `.nexara/PROJECT_FACTS.json` | FROZEN |
| Baseline | `.nexara/BASELINE.json` | FROZEN |
| Blockers | `.nexara/KNOWN_BLOCKERS.json` | ACTIVE |
| Decisions | `.nexara/DECISION_LOG.md` | ACTIVE |

**Rule:** All future Claude sessions MUST read Constitution → Gate DAG → GATE_STATUS.json. Chat history is not program authority.

## 2. 命名 (Naming) — FROZEN

| Scope | Value | Status |
|-------|-------|--------|
| Platform | `NEXARA_PRIME` | FROZEN |
| Program | `NEXARA_FIRST_PARTY_SOVEREIGN_AGENT` | FROZEN |
| Agent package | `nexara_prime.agent` | FROZEN |
| Python package | `nexara-prime==0.1.0` | FROZEN |
| CLI entry point | `nexara` | FROZEN |
| Product brand name | **待定 — human decision required** | PENDING |

**Naming convention:** `nexara_prime` for all Python namespaces. Agent domain services under `src/nexara_prime/agent/`. Platform services under `src/nexara_prime/platform/`. Kernel under `src/nexara_prime/` (existing).

## 3. 主权边界 (Sovereignty Boundaries) — FROZEN

Per Constitution §§1-4:

| Boundary | Rule |
|----------|------|
| Human sovereignty | User owns goals, approval, takeover, revocation, rollback |
| Agent identity | `agent_id`, profile, memory namespace owned by platform, not model |
| Model independence | Models are replaceable reasoning resources; they do not own AgentIdentity, Mission, Memory, Policy, or Evidence |
| Hermes/Claude/Codex | Build-time executors only. NOT in product runtime dependency. Verified: 0 imports. |
| Persona.HERMES | String constant in `models.py:111` — legacy naming. Flagged for G1 rename. No functional dependency. |
| R0-R4 policy | Deny-by-default. R3/R4 require human approval. |
| Secret scope | macOS Keychain + env vars. No hardcoded secrets. Verified: 0 findings. |

## 4. 对象/事件/API 兼容基线 (Compatibility Baseline) — FROZEN

### Schemas (4 files, JSON Schema)

| Schema | $id | Status |
|--------|-----|--------|
| `schemas/event.json` | event | FROZEN |
| `schemas/evidence_artifact.json` | evidence_artifact | FROZEN |
| `schemas/mission_spec.json` | mission_spec | FROZEN |
| `schemas/work_contract.json` | work_contract | FROZEN |

### Core Models (`src/nexara_prime/models.py`)

| Model | schema_version | Status |
|-------|---------------|--------|
| MissionSpec | — | FROZEN |
| WorkContract | 1 | FROZEN |
| PlanStep / MissionPlan | — | FROZEN |
| AgentAssignment | 1 | FROZEN |
| EvidenceEnvelope | 1 | FROZEN |
| MemoryItem | 2 | FROZEN |
| PolicyDecision | 1 | FROZEN |
| CapabilityManifest | 1 | FROZEN |
| ToolContract | 1 | FROZEN |

### API Surface (`src/nexara_prime/api.py`)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/health` | GET | FROZEN |
| `/api/runtime/overview` | GET | FROZEN |
| `/api/missions` | GET/POST | FROZEN |
| `/api/missions/{id}` | GET | FROZEN |
| `/api/missions/{id}/plan` | POST | FROZEN |
| `/api/missions/{id}/approve` | POST | FROZEN |
| `/api/missions/{id}/run` | POST | FROZEN |
| `/api/missions/{id}/pause` | POST | FROZEN |

**Compatibility rule:** G1+ may ADD fields (with defaults) and ADD endpoints. Must NOT remove or rename existing fields/endpoints without migration. schema_version must be incremented on breaking changes.

## 5. 非目标 (Non-Goals) — FROZEN

Per Blueprint §1.2, this program does NOT build:

1. **Not a Hermes/Claude/Codex wrapper.** NEXARA PRIME is a first-party sovereign agent, not a re-skinned external framework.
2. **Not a chatbot UI.** The product surface is Mission Composer + Workspace, not a chat window.
3. **Not a fixed 8-role performance system.** Roles are dynamically generated per mission, not a static cast.
4. **Not a "plan-only" tool.** Every mission must execute, verify, and produce evidence — planning is necessary but insufficient.
5. **Not an automation script that bypasses human approval.** R3/R4 actions require explicit approval with binding evidence.
6. **Not a multi-agent marketplace (yet).** First-party agent comes first. SDK/plugin ecosystem is G8.
7. **Not a cloud-dependent service.** Local-first with SQLite/Keychain/DuckDB. Cloud is optional migration, not default.
8. **Not a model=identity system.** Models are tools. Agent identity, memory, and policy persist across model changes.
