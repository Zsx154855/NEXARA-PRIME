# NEXARA Control Plane — Boundary Definition

> Phase 13 Product Architecture | Control Plane V1.0

## Architecture Principle

```
┌─────────────────────────────────────────────────┐
│                  CONTROL PLANE                   │
│              (Human Governance UI)               │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Mission  │ │ Evidence │ │   Governance     │ │
│  │ Control  │ │ Explorer │ │   Console        │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │             │               │           │
│       └─────────────┼───────────────┘           │
│                     │                           │
│              READ-ONLY API                      │
│         (except human actions)                  │
└─────────────────────┬───────────────────────────┘
                      │
              ┌───────┴────────┐
              │  RUNTIME API   │
              │  (FastAPI)     │
              └───────┬────────┘
                      │
┌─────────────────────┴───────────────────────────┐
│                  RUNTIME PLANE                   │
│              (NexaraRuntime)                     │
│                                                  │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Models  │ │Evidence  │ │  State Machine   │  │
│  │ Gateway │ │ Store    │ │  + Governance    │  │
│  └─────────┘ └──────────┘ └──────────────────┘  │
│                                                  │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Memory  │ │  Tools   │ │  Recovery        │  │
│  │ Kernel  │ │ Runtime  │ │  + Checkpoint    │  │
│  └─────────┘ └──────────┘ └──────────────────┘  │
│                                                  │
│              SQLiteStore (DB)                    │
└──────────────────────────────────────────────────┘
```

## Control Plane Permissions

### YES — Allowed Actions

| Action | API Endpoint | Rationale |
|--------|-------------|-----------|
| Query mission list | `GET /api/missions` | Read-only observation |
| Inspect mission detail | `GET /api/missions/{id}` | Full transparency |
| View evidence chain | `GET /api/evidence` | Audit trail |
| View tool invocations | `GET /api/tools` | Tool traceability |
| View memory state | `GET /api/memory` | Knowledge inspection |
| View approval list | `GET /api/approvals` | Governance visibility |
| View event timeline | `GET /api/events/{id}` | Temporal audit |
| View runtime health | `GET /health`, `/api/runtime/overview` | Operational awareness |
| View adaptive status | `GET /adaptive/*` | Runtime monitoring |
| Create mission | `POST /api/missions` | Human-initiated work |
| Approve/reject mission | `POST /api/missions/{id}/approve` | Human governance gate |
| Pause mission | `POST /api/missions/{id}/pause` | Operational control |
| Resume mission | `POST /api/missions/{id}/resume` | Operational control |
| Rollback mission | `POST /api/missions/{id}/rollback` | Failure recovery |
| Toggle safe mode | `POST /api/missions/{id}/safe-mode` | Safety control |
| Trigger recovery check | `POST /api/recovery/check` | System health |

### NO — Forbidden Actions

| Action | Rationale |
|--------|-----------|
| Direct database modification | Violates DB authority (SQLiteStore only) |
| Direct mission state mutation | Must go through state machine TRANSITIONS matrix |
| Bypass Capability Registry | All tool access must be capability-gated |
| Bypass Approval Engine | Governance integrity (NSEC Article 37) |
| Direct evidence writing | EvidenceStore is the single authority |
| Direct tool execution | ToolRuntime governs all invocations |
| Direct memory patching | MemoryKernel governs all patches |
| Modify Core Contracts | Frozen at 8a75910 |
| Modify Runtime Contracts | Sealed at ceae37f |
| Create new Runtime capabilities | Requires NSEC governance change |

## Data Flow

```
┌──────────────────┐
│  CONTROL PLANE   │
│  (Next.js SPA)   │
└────────┬─────────┘
         │ HTTP fetch
         ▼
┌──────────────────┐
│  FastAPI Server  │  ← runtime.api module
│  /api/*          │
│  /adaptive/*     │
└────────┬─────────┘
         │ Python call
         ▼
┌──────────────────┐
│  NexaraRuntime   │  ← runtime.py
│  .inspect_mission│
│  .evidence.list  │
│  .approvals.list │
│  .events.replay  │
│  .memory.inspect │
│  .tools.list_    │
│  .overview()     │
│  .health()       │
└────────┬─────────┘
         │ Python call
         ▼
┌──────────────────┐
│  SQLiteStore     │  ← db.py (single authority)
│  (nexara.db)     │
└──────────────────┘
```

## Invariant Protection

The Control Plane MUST NOT violate any Runtime Invariant:

1. ❌ No silent MockProvider fallback
2. ❌ No raw store.find_record bypass
3. ❌ No self-transitions (stages advance forward only)
4. ❌ No state regression (resume only unpauses)
5. ❌ No duplicate side effects
6. ❌ Approval integrity (starts as integrity_error)
7. ❌ Evidence integrity (verify before rely)
8. ❌ Provider unavailable is resumable
9. ❌ Adaptive states rejected
10. ❌ SDK compatibility inline

## Implementation Boundary

The Control Plane is a **pure frontend application**:
- Framework: Next.js 16 (matches project tech stack)
- Data access: Runtime REST API only
- State: React local state + SWR/React Query for caching
- No backend code in Control Plane
- No new Python modules
- No new database tables
- No new Runtime services
