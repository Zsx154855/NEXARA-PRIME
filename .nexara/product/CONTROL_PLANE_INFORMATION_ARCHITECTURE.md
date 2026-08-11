# NEXARA Control Plane V1 — Information Architecture

> Phase 13 Product Architecture | Version 1.0

## Architecture Overview

```
NEXARA CONTROL PLANE V1
│
├── Dashboard (Overview)
│   ├── System Health Card
│   ├── Active Missions Summary
│   ├── Pending Approvals
│   └── Recent Activity Feed
│
├── Mission Control
│   ├── Mission List
│   │   ├── Filter by State / Risk / Date
│   │   ├── Search by Objective / ID
│   │   └── Quick Actions (Pause / Resume / Rollback)
│   │
│   └── Mission Detail
│       ├── Overview Tab (DNA)
│       ├── Contract Tab
│       ├── Plan Tab
│       ├── Execution Tab (Timeline)
│       ├── Evidence Tab
│       ├── Memory Tab
│       └── Evaluation Tab
│
├── Evidence Explorer
│   ├── Evidence List
│   │   ├── Filter by Mission / Type / Actor
│   │   └── Search by Hash
│   │
│   └── Evidence Detail
│       ├── Artifact Content
│       ├── Hash Verification
│       ├── Actor Chain
│       └── Receipt Status
│
├── Governance Console
│   ├── Approval Queue
│   │   ├── Pending Approvals
│   │   ├── Approval History
│   │   └── Approve / Reject Actions
│   │
│   ├── Policy Viewer
│   │   ├── Active Policies
│   │   └── Policy Audit Trail
│   │
│   └── Audit Log
│       ├── Event Timeline
│       ├── Filter by Actor / Action
│       └── Export Evidence
│
└── Runtime Health
    ├── Provider Status
    ├── Worker Pool
    ├── Queue Depth
    ├── Resource Usage
    └── Recovery Status
```

---

## 1. Dashboard (Overview)

**Purpose**: Single-glance operational awareness.

### Data Sources
- `GET /api/runtime/overview` → system info, recent missions, approvals, evidence, tools, capabilities, recovery
- `GET /health` → provider, db_path, event_count
- `GET /adaptive/status` → adaptive runtime state

### Key Metrics Displayed
- System status (healthy/degraded/unavailable)
- Provider name and model mode
- Active mission count by state
- Pending approval count
- Evidence count (last 24h)
- Recovery status

### Empty State
- "No missions yet — create your first mission to begin."

---

## 2. Mission Control

### 2.1 Mission List

**Purpose**: Browse, search, and manage all missions.

**Data Source**: `GET /api/missions`

**Display Fields per Row**:
- Mission ID (truncated, clickable)
- Objective (title)
- State (with color badge)
- Risk Level (R0-R4)
- Created At
- Approval Status
- Evidence Count

**Filters**:
- State: Intent / Contract / Plan / Execution / Completed / Failed / Blocked
- Risk: R0 / R1 / R2 / R3 / R4
- Date range

**Sort**: Created At (default: newest first)

**Quick Actions (per row)**:
- Pause / Resume (if applicable)
- Rollback (if applicable)
- View Detail →

**Empty State**:
- "No missions match your filters."

### 2.2 Mission Detail

**Purpose**: Complete mission transparency — from intent to completion.

**Data Source**: `GET /api/missions/{id}` (inspect_mission)

**Tabs**:

#### Overview Tab (DNA)
```
┌─────────────────────────────────────────┐
│  Mission DNA                            │
│                                         │
│  ID:       mission_xxxxxxxxxxxx         │
│  State:    Execution                    │
│  Risk:     R2                           │
│  Created:  2026-08-09 01:25 UTC         │
│  Updated:  2026-08-09 01:30 UTC         │
│  Provider: deepseek                     │
│  Trace ID:  trace_xxxxxxxxxxxx          │
│                                         │
│  Objective:                             │
│  "Fix the authentication bug..."        │
│                                         │
│  Status Indicators:                     │
│  ● Approval: pending                    │
│  ● Evidence: 12 items                   │
│  ● Memory: patched                      │
│  ● Evaluation: passed                   │
│  ● Receipt: verified                    │
│  ● Safe Mode: off                       │
│  ● Paused: no                           │
│  ● Retries: 2                           │
└─────────────────────────────────────────┘
```

#### Contract Tab
- MissionSpec fields (from `spec` in inspect_mission)
- Source directory
- Risk level rationale
- Capability requirements

#### Plan Tab
- MissionPlan steps (from `plan` in inspect_mission)
- Step sequence with status indicators
- Agent assignments per step

#### Execution Tab (Timeline)
- **Data Source**: `GET /api/events/{id}` → chronological event list
- State transitions with timestamps
- Tool invocations inline
- Evidence additions inline
- Approval events
- Memory patches

**Visual**: Vertical timeline with state-colored nodes.

#### Evidence Tab
- **Data Source**: `GET /api/evidence?mission_id={id}`
- Evidence list with type, actor, timestamp
- Hash verification status
- Receipt chain status

#### Memory Tab
- **Data Source**: `GET /api/memory?mission_id={id}`
- Memory records created by this mission
- Memory patch status
- Knowledge objects referenced
- Candidates for patching

#### Evaluation Tab
- Evaluation result (passed/failed/not_evaluated)
- Evaluation criteria
- Score breakdown (if available)

---

## 3. Evidence Explorer

**Purpose**: Cross-mission evidence audit and chain verification.

### 3.1 Evidence List

**Data Source**: `GET /api/evidence`

**Display Fields**:
- Evidence ID
- Mission ID (link)
- Type (state_change / tool_invocation / memory_patch / ...)
- Actor
- Timestamp
- Hash (truncated)

**Filters**:
- Mission ID
- Evidence Type
- Actor (human / reviewer / archivist / kairos)
- Date range

### 3.2 Evidence Detail

**Data Source**: Evidence artifact content from `GET /api/evidence`

**Display**:
- Full artifact content (JSON pretty-printed)
- SHA-256 hash with copy button
- Actor identity and type
- Verification status
- Receipt chain position

### 3.3 Receipt Verification

**Data Source**: `GET /api/receipts?mission_id={id}`

**Display**:
- Chain verification status (verified / broken / missing)
- Chain length
- Each receipt with hash and link

---

## 4. Governance Console

### 4.1 Approval Queue

**Purpose**: Human governance — review and act on pending approvals.

**Data Source**: `GET /api/approvals`

**Pending Approvals Display**:
- Approval ID
- Mission ID (link to detail)
- Requested at
- Status (pending / approved / rejected)
- Mission objective (context)
- **Action buttons**: Approve / Reject (with note field)

**Approval History**:
- All past approvals with status, actor, note, timestamp

### 4.2 Policy Viewer

**Purpose**: Display active governance policies (read-only).

**Data Source**: `GET /api/runtime/overview` → capabilities, system info

**Display**:
- Active NSEC version
- Capability registry state
- Runtime mode
- Human control status
- Safe mode status

### 4.3 Audit Log

**Purpose**: Full temporal audit trail.

**Data Source**: `GET /api/events/{id}` (per mission) or aggregated

**Display**:
- Chronological event feed
- Color-coded by event type
- Filter by actor, action, mission
- Export capability (JSON dump)

---

## 5. Runtime Health

**Purpose**: Operational monitoring of the runtime itself.

**Data Sources**:
- `GET /health` → provider, db_path, event_count, recovery
- `GET /api/runtime/overview` → adapters, capabilities
- `GET /adaptive/status` → adaptive runtime state
- `GET /adaptive/missions/{id}/budget` → per-mission resource usage

**Display Panels**:

### Provider Status
- Provider name
- Mock mode on/off
- Provider availability
- Circuit breaker state

### Worker Pool
- Active workers
- Queue depth
- Completed / Failed counts

### Resource Usage
- Token budget vs used (per mission, aggregated)
- Tool call counts
- Retry counts

### Recovery Status
- Last recovery check timestamp
- Recovery state
- Pending recovery items

---

## 6. Navigation Structure

```
Sidebar Navigation
├── ⌂  Dashboard
├── ◉  Missions
│   ├── All Missions
│   └── + New Mission
├── ◈  Evidence
├── ⚖  Governance
│   ├── Approvals
│   ├── Policies
│   └── Audit Log
└── ⚙  Health

Top Bar
├── Project Title: "NEXARA PRIME"
├── Runtime Status Indicator (green/yellow/red dot)
└── Last Updated timestamp

Footer
├── NSEC V2.1
├── HEAD: ceae37f
└── Branch: feat/brand-baihan
```

---

## 7. Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| ≥ 1024px | Sidebar + content (desktop) |
| 768-1023px | Collapsible sidebar (tablet) |
| < 768px | Bottom tab bar (mobile — secondary priority) |

Desktop-first design. Mobile is informational only (no complex operations).
