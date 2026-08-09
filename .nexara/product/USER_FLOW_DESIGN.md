# NEXARA Control Plane V1 — User Flow Design

> Phase 13 Product Architecture | Version 1.0

---

## FLOW 1: Human Creates Mission

### Entry Point
Dashboard → "New Mission" button or Mission Control → "+ New Mission"

### Flow

```
[Human]

   │
   ▼
┌─────────────────────────────┐
│  1. Enter Mission Objective │
│  ┌───────────────────────┐  │
│  │ "Fix authentication    │  │
│  │  timeout in login..."  │  │
│  └───────────────────────┘  │
│                             │
│  Source Directory (optional)│
│  ┌───────────────────────┐  │
│  │ /path/to/project       │  │
│  └───────────────────────┘  │
│                             │
│  [Create Mission]  [Cancel] │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  2. POST /api/missions      │
│  → Runtime.create_mission() │
│  → MissionState.INTENT     │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  3. Redirect to Mission     │
│     Detail Page             │
│     (/missions/{id})        │
│                             │
│  Next actions:              │
│  [Plan] → FLOW 1b           │
│  [Run]  → FLOW 3            │
└─────────────────────────────┘
```

### States
- **Loading**: Spinner on "Create Mission" button
- **Error**: Toast: "Failed to create mission: {error}"
- **Empty**: Pre-condition — no error state, form always ready

### Edge Cases
- Empty objective → disable submit button, show "Objective is required"
- Source directory invalid → show validation error from API
- Network error → retry prompt

---

## FLOW 1b: Human Plans Mission

### Entry Point
Mission Detail → "Plan" button (visible when state = INTENT or CONTEXT)

### Flow

```
[Mission Detail — State: INTENT]

   │ [Plan] clicked
   ▼
┌─────────────────────────────┐
│  POST /api/missions/{id}/   │
│       plan                  │
│  → Runtime.plan_mission()   │
│  → CONTEXT → CONTRACT →     │
│    PLAN → SIMULATION →      │
│    APPROVAL                 │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  State updated to APPROVAL  │
│                             │
│  Plan tab now populated     │
│  with step sequence         │
│                             │
│  Next:                      │
│  [Approve] → FLOW 2         │
│  [Run]    → FLOW 3          │
└─────────────────────────────┘
```

### States
- **Loading**: Full-page overlay with "Planning mission..." + progress spinner
- **Error**: Toast: "Planning failed: {reason}"
- **Success**: Plan tab animates in; state badge updates to APPROVAL

---

## FLOW 2: Approval

### Entry Point
Mission Detail (state = APPROVAL) → "Approve" button
Governance Console → Approval Queue → specific approval

### Flow

```
┌─────────────────────────────┐
│  Approval Required          │
│                             │
│  Mission: {objective}       │
│  State:   APPROVAL          │
│  Risk:    R2                │
│                             │
│  ┌───────────────────────┐  │
│  │ Review Plan           │  │
│  │ - Step 1: ...         │  │
│  │ - Step 2: ...         │  │
│  │ - Step 3: ...         │  │
│  └───────────────────────┘  │
│                             │
│  Note (optional):           │
│  ┌───────────────────────┐  │
│  │ "Looks good, proceed." │  │
│  └───────────────────────┘  │
│                             │
│  [Approve]    [Reject]      │
└─────────────┬───────────────┘
              │
     ┌────────┴────────┐
     ▼                 ▼
┌─────────┐     ┌─────────────┐
│ APPROVE │     │   REJECT     │
│         │     │              │
│ POST    │     │ POST         │
│ /api/   │     │ /api/        │
│ missions│     │ missions     │
│ /{id}/  │     │ /{id}/       │
│ approve │     │ approve      │
│ {       │     │ {            │
│  appro- │     │  approved:   │
│  ved:   │     │  false,      │
│  true,  │     │  note:       │
│  note:  │     │  "Needs      │
│  "..."  │     │  revision"   │
│ }       │     │ }            │
└────┬────┘     └──────┬───────┘
     │                 │
     ▼                 ▼
┌─────────┐     ┌─────────────┐
│ State → │     │ State →     │
│ EXECUT- │     │ BLOCKED     │
│ ION     │     │             │
│         │     │ Terminal    │
│ Next:   │     │ reason:     │
│ [Run]   │     │ "Rejected"  │
└─────────┘     └─────────────┘
```

### States
- **Loading**: Button shows spinner
- **Error**: Toast with API error message
- **Success (Approve)**: State badge turns green EXECUTION; "Run" button appears
- **Success (Reject)**: State badge turns red BLOCKED; terminal reason displayed

### Edge Cases
- Approval already processed → show "Already processed" message
- Permission denied → "You are not authorized" (NSEC Article 37)
- Approval expired → show expiry details

---

## FLOW 3: Execution Monitoring

### Entry Point
Mission Detail (state = EXECUTION) → "Run" button

### Flow

```
┌─────────────────────────────┐
│  Mission: EXECUTION         │
│                             │
│  [Run] clicked              │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  POST /api/missions/{id}/   │
│       run                   │
│  → Runtime.run_mission()    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Polling Loop               │
│                             │
│  GET /api/missions/{id}     │
│  (every 2s)                 │
│                             │
│  ┌───────────────────────┐  │
│  │ EXECUTION → VERIFY    │──┤
│  │ → EVIDENCE → MEMORY   │  │
│  │ → EVALUATION →        │  │
│  │ COMPLETED              │  │
│  └───────────────────────┘  │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Execution Timeline         │
│                             │
│  ○ 01:25  EXECUTION start   │
│  │  Tool: file_read         │
│  │  Tool: grep_search       │
│  ○ 01:26  VERIFICATION      │
│  │  Evidence: state_change  │
│  ○ 01:27  EVIDENCE          │
│  │  Evidence: receipt       │
│  ○ 01:28  MEMORY_PATCH      │
│  │  Memory: patch_id=...    │
│  ○ 01:29  EVALUATION        │
│  ● 01:30  COMPLETED ✓       │
└─────────────────────────────┘

During execution, user can:
  [Pause] → pause mission
  [Safe Mode] → toggle safe mode
```

### States
- **Active execution**: Polling indicator + live timeline updates
- **Paused**: "Paused" badge; [Resume] button
- **Completed**: Green "COMPLETED" badge; evaluation result shown
- **Failed**: Red "FAILED" badge; terminal reason displayed
- **Provider Unavailable**: Yellow warning; auto-retry indicator

### Interaction During Execution
| Action | Available When | Effect |
|--------|---------------|--------|
| Pause | EXECUTION, VERIFICATION | State → PAUSED |
| Resume | PAUSED | State → previous state |
| Safe Mode | Any running state | Toggles safe_mode flag |
| Rollback | COMPLETED, FAILED, BLOCKED | State → ROLLED_BACK |

---

## FLOW 4: Failure Recovery

### Entry Point
Mission Detail (state = FAILED or BLOCKED)

### Flow

```
┌─────────────────────────────┐
│  Mission: FAILED            │
│                             │
│  Terminal Reason:           │
│  "Provider unavailable      │
│   after 3 retries"          │
│                             │
│  Evidence chain intact: ✓   │
│  Recovery pointer: step_3   │
│  Retry count: 3             │
│                             │
│  ┌───────────────────────┐  │
│  │ Recovery Options      │  │
│  │                       │  │
│  │ [Retry]  [Rollback]   │  │
│  └───────────────────────┘  │
└─────────────┬───────────────┘
              │
     ┌────────┴────────┐
     ▼                 ▼
┌─────────┐     ┌─────────────┐
│ RETRY   │     │  ROLLBACK   │
│         │     │             │
│ Creates │     │ POST        │
│ new     │     │ /api/       │
│ mission │     │ missions    │
│ (manual)│     │ /{id}/      │
│         │     │ rollback    │
│         │     │             │
│ Human   │     │ State →     │
│ reviews │     │ ROLLED_BACK │
│ evidence│     │             │
│ first   │     │ Evidence:   │
└─────────┘     │ rollback_   │
                │ point       │
                └─────────────┘
```

### Additional Recovery Actions
- **Recovery Check**: `POST /api/recovery/check` → runtime.recover()
- Display recovery state, pending items
- Evidence review before any retry/rollback decision

### States
- **FAILED**: Red badge, terminal reason, recovery options visible
- **BLOCKED**: Orange badge, blocker reason, recovery options visible
- **ROLLED_BACK**: Gray badge, rollback checkpoint evidence displayed
- **Recovery in progress**: Spinner on recovery check

---

## FLOW 5: Evidence Audit

### Entry Point
Evidence Explorer or Mission Detail → Evidence Tab

### Flow

```
┌─────────────────────────────┐
│  Evidence Explorer          │
│                             │
│  Filters:                   │
│  [Mission: all ▾]           │
│  [Type: all ▾]             │
│  [Date: last 7 days ▾]     │
│                             │
│  Evidence List              │
│  ┌───────────────────────┐  │
│  │ ● state_change 01:25  │  │
│  │ ● tool_invoc   01:26  │  │
│  │ ● state_change 01:27  │  │
│  │ ● receipt      01:28  │  │
│  │ ...                   │  │
│  └───────────────────────┘  │
└─────────────┬───────────────┘
              │ Click evidence item
              ▼
┌─────────────────────────────┐
│  Evidence Detail            │
│                             │
│  Type:    tool_invocation   │
│  Actor:   reviewer          │
│  Time:    2026-08-09 01:26  │
│  Hash:    sha256:abc123...  │
│           [Copy] [Verify]   │
│                             │
│  Content:                   │
│  ┌───────────────────────┐  │
│  │ {                     │  │
│  │   "tool": "file_read",│  │
│  │   "path": "...",      │  │
│  │   "result": "..."     │  │
│  │ }                     │  │
│  └───────────────────────┘  │
│                             │
│  Receipt Chain:             │
│  ● Verified ✓              │
│  ● Chain length: 4         │
│  [View Full Chain]          │
└─────────────────────────────┘
```

---

## FLOW 6: Runtime Health Check

### Entry Point
Sidebar → Health

### Flow

```
┌─────────────────────────────┐
│  Runtime Health             │
│                             │
│  ┌─────────┐ ┌────────────┐ │
│  │ Provider│ │ Workers    │ │
│  │         │ │            │ │
│  │ deepseek│ │ Active: 2  │ │
│  │ ● Online│ │ Queue: 0   │ │
│  │         │ │ Done: 47   │ │
│  └─────────┘ └────────────┘ │
│                             │
│  ┌─────────┐ ┌────────────┐ │
│  │ Adapters│ │ Resources  │ │
│  │         │ │            │ │
│  │ Browser │ │ Tokens:    │ │
│  │  ✓      │ │ 12.4K/50K │ │
│  │ Git  ✓  │ │ Tools: 47  │ │
│  │ CI   ✓  │ │ Retries: 3 │ │
│  └─────────┘ └────────────┘ │
│                             │
│  ┌───────────────────────┐  │
│  │ Recovery              │  │
│  │ State: healthy        │  │
│  │ Last check: 01:25     │  │
│  │ [Check Now]           │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

---

## Global Error Handling

| Error Type | UI Response |
|-----------|-------------|
| Network error | Full-page "Connection Lost" + retry button |
| API 404 | "Resource not found" card |
| API 400 | Toast with specific error message |
| API 500 | "Runtime error" card + recovery check button |
| Provider unavailable | Yellow banner: "Provider unavailable — missions will retry automatically" |
| Timeout | Toast: "Request timed out" |

## Global Loading States

| Context | Loading Indicator |
|---------|------------------|
| Page navigation | Top bar progress line (thin, subtle) |
| Data fetch | Skeleton cards (gray placeholders) |
| Action (create, approve, etc.) | Button spinner |
| Polling (execution monitoring) | Pulsing dot on state badge |
| Full page load | Centered spinner with app logo |
