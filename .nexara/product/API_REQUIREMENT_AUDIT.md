# NEXARA Control Plane V1 — API Requirement Audit

> Phase 13 Product Architecture | Version 1.0

## Audit Principle

**Prefer KEEP over EXTEND. Prefer EXTEND over NEW. No REJECT without justification.**

The Runtime API (26 endpoints in api.py) was designed before the Control Plane existed. We audit each endpoint against Control Plane needs and classify accordingly.

---

## Classification Summary

| Classification | Count | Meaning |
|---------------|-------|---------|
| KEEP | 20 | Existing endpoint fully satisfies Control Plane need |
| EXTEND | 5 | Existing endpoint needs minor field additions |
| NEW | 1 | Genuinely new endpoint required |
| REJECT | 1 | Endpoint not needed for Control Plane |

---

## Endpoint-by-Endpoint Audit

### KEEP (20 endpoints — no changes required)

| # | Endpoint | Control Plane Usage |
|---|----------|-------------------|
| 1 | `GET /health` | Health dashboard — provider, event count, recovery |
| 2 | `GET /api/runtime/overview` | Dashboard overview — system info, recent missions, approvals, evidence, tools, capabilities, recovery |
| 3 | `GET /api/missions` | Mission Control — list all missions with state/risk/date |
| 4 | `POST /api/missions` | Mission Control — create new mission from UI |
| 5 | `GET /api/missions/{id}` | Mission Detail — complete inspect_mission snapshot |
| 6 | `POST /api/missions/{id}/plan` | Mission Detail — trigger mission planning |
| 7 | `POST /api/missions/{id}/approve` | Governance Console — approve/reject from UI |
| 8 | `POST /api/missions/{id}/run` | Mission Detail — execute approved mission |
| 9 | `POST /api/missions/{id}/pause` | Mission Detail — pause running mission |
| 10 | `POST /api/missions/{id}/resume` | Mission Detail — resume paused mission |
| 11 | `POST /api/missions/{id}/rollback` | Mission Detail — rollback failed/blocked mission |
| 12 | `POST /api/missions/{id}/safe-mode` | Mission Detail — toggle safe mode |
| 13 | `GET /api/evidence` | Evidence Explorer — list evidence (optionally filtered by mission) |
| 14 | `GET /api/memory` | Mission Detail / Memory tab — inspect memory |
| 15 | `GET /api/memory/candidates` | Mission Detail / Memory tab — patch candidates |
| 16 | `GET /api/events/{id}` | Mission Detail / Execution Timeline — event replay |
| 17 | `GET /api/tools` | Evidence Explorer — tool invocation list |
| 18 | `GET /adaptive/status` | Runtime Health — adaptive runtime state |
| 19 | `GET /adaptive/missions/{id}/budget` | Runtime Health — per-mission resource usage |
| 20 | `POST /api/recovery/check` | Runtime Health — trigger recovery check |

---

### EXTEND (5 endpoints — add fields to existing response)

#### E1: `GET /api/missions` — Add mission summary fields

**Why EXTEND**: Currently returns `list_missions()` which has limited fields. Control Plane mission list needs state, risk_level, objective, created_at for each mission in the list view without N+1 API calls.

**Current**: `list_missions()` returns minimal dict per mission.

**Requested additions**:
- `state` (already present via inspect_mission path in /api/runtime/overview, but not in /api/missions)
- `risk_level`
- `objective` (title)
- `created_at`
- `evidence_count`
- `approval_status`

**Impact**: Add 5 fields to `list_missions()` return dict in runtime.py. Trivial — all data already in Mission object.

**Permission**: Read-only, no governance impact.

---

#### E2: `GET /api/missions/{id}` — Add plan step count and capability list

**Why EXTEND**: `inspect_mission` returns plan as full dict but no summary metadata. Control Plane needs step count without parsing entire plan.

**Requested additions**:
- `plan_step_count`: int (from `len(mission.plan.steps)` if plan exists)
- `capabilities_required`: list[str] (from `mission.spec.capabilities`)

**Impact**: Add 2 computed fields to `inspect_mission()` return dict. Trivial.

**Permission**: Read-only.

---

#### E3: `GET /api/approvals` — Add mission context fields

**Why EXTEND**: Approval queue needs mission objective context without N+1 API calls to inspect each mission.

**Requested additions per approval item**:
- `mission_objective`: str (the mission's objective/title)
- `mission_risk_level`: str
- `mission_state`: str

**Impact**: Enrich approval list items with joined mission data. Simple — approvals already have `mission_id`.

**Permission**: Read-only.

---

#### E4: `GET /api/runtime/overview` — Add aggregated statistics

**Why EXTEND**: Dashboard needs quick stats without aggregating client-side.

**Requested additions**:
- `stats`: { `total_missions`, `active_missions`, `completed_missions`, `failed_missions`, `pending_approvals`, `total_evidence` }

**Impact**: Add one computed dict to `overview()` return. All data is already in the overview response — just needs pre-aggregation.

**Permission**: Read-only.

---

#### E5: `GET /api/missions/{id}` — Add terminal_reason details for FAILED/BLOCKED

**Why EXTEND**: When mission is FAILED or BLOCKED, Control Plane needs structured recovery information.

**Current**: `terminal_reason` is a plain string from `mission.result.get("error")`.

**Requested additions**:
- `failure_code`: str | None (from FailureCode enum if stored)
- `retry_count`: int (already present ✅)
- `recovery_pointer`: str | None (already present ✅)
- `provider_unavailable`: bool (already present ✅)
- `last_evidence_timestamp`: str | None

**Impact**: Add 2 fields (`failure_code`, `last_evidence_timestamp`). Most already exist.

**Permission**: Read-only.

---

### NEW (1 endpoint)

#### N1: `GET /api/runtime/stats` — Aggregated runtime statistics

**Why NEW**: Control Plane dashboard needs a single lightweight endpoint that returns aggregated counts without the full overview payload (which includes 20-item arrays for missions, approvals, evidence, tools).

**Rationale**: The existing `/api/runtime/overview` returns full arrays. For a dashboard polling scenario (every 10s), we want a < 1KB response.

**Request**:
```
GET /api/runtime/stats
```

**Response**:
```json
{
  "total_missions": 47,
  "active_missions": 3,
  "completed_missions": 38,
  "failed_missions": 4,
  "blocked_missions": 2,
  "pending_approvals": 1,
  "total_evidence": 312,
  "provider": "deepseek",
  "provider_available": true,
  "mock_mode": false,
  "recovery_state": "healthy",
  "last_event_at": "2026-08-09T01:25:00Z"
}
```

**Implementation**: Add `def stats(self) -> dict` to NexaraRuntime that aggregates from store. Simple counts, no complex queries.

**Permission**: Read-only. No evidence required (no state mutation).

---

### REJECT (1 endpoint)

#### R1: `GET /api/knowledge-universe` — Deferred to future phase

**Why REJECT**: Knowledge Universe is a separate product surface (already mounted at `/knowledge-universe`). Not part of Control Plane V1 scope. The existing mount point at api.py:226 serves it independently.

**Decision**: Do NOT integrate into Control Plane V1. Can be added as a linked external page or in a future phase.

---

## Summary

| Category | Count | Runtime Impact |
|----------|-------|---------------|
| KEEP | 20 | None |
| EXTEND | 5 | Add 11 total fields across 5 endpoints (trivial) |
| NEW | 1 | Add `stats()` method + 1 route (simple) |
| REJECT | 1 | None |

**Total Runtime Change**: Approximately 30 lines of Python added (field enrichment + 1 new method + 1 new route). Zero changes to Core Contracts, State Machine, DB Schema, or Capability Registry.

**Implementation Order** (when UI coding begins):
1. E1 (list mission fields) — needed immediately for Mission List
2. E2 (plan step count) — needed for Mission Detail
3. N1 (stats endpoint) — needed for Dashboard
4. E4 (overview stats) — alternative to N1, decide which to implement
5. E3 (approval context) — needed for Approval Queue
6. E5 (failure details) — needed for recovery flows

**Preference**: Implement N1 over E4; N1 is cleaner (single-purpose stats endpoint vs mixing stats into overview). Both are valid — implementation choice during UI coding phase.
