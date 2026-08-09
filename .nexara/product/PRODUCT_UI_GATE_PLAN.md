# NEXARA Control Plane V1 — Product UI Gate Plan

> Phase 13 Product Architecture | Version 1.0

## Gate Philosophy

Each gate MUST pass before entering UI implementation. Gates are verified against the SEALED Runtime V1.0 baseline at `ceae37f`. No gate can be waived. No "conditional pass" allowed.

---

## Gate 1: Architecture Alignment

### Question
Does the Control Plane design respect the Core Freeze and Runtime Seal?

### Check Items

| # | Check | Expected | Status |
|---|-------|----------|--------|
| 1.1 | Frozen files unchanged? | 16/16 frozen files untouched | ✅ |
| 1.2 | No new Python modules required? | Control Plane is pure frontend | ✅ |
| 1.3 | No new DB tables? | SQLiteStore unchanged | ✅ |
| 1.4 | No new Runtime services? | NexaraRuntime unchanged | ✅ |
| 1.5 | No Core Contract modification? | models.py / state_machine.py unchanged | ✅ |
| 1.6 | API extends (not replaces) existing? | 20 KEEP, 5 EXTEND, 1 NEW, 1 REJECT | ✅ |
| 1.7 | Control Plane / Runtime boundary clear? | CONTROL_PLANE_BOUNDARY.md defines explicit YES/NO matrix | ✅ |

### Verdict: **PASS** ✅

---

## Gate 2: Runtime Contract Compliance

### Question
Does the Control Plane respect all 10 Runtime Invariants?

### Check Items

| # | Invariant | Control Plane Compliance |
|---|-----------|-------------------------|
| 2.1 | No silent MockProvider fallback | Control Plane reads provider status; never sets it |
| 2.2 | No raw store.find_record bypass | All data access through Runtime API |
| 2.3 | No self-transitions | Only calls Runtime methods that go through state machine |
| 2.4 | No state regression | pause()/resume() only |
| 2.5 | No duplicate side effects | Idempotent GET requests; POST actions are user-initiated |
| 2.6 | Approval integrity | Uses approve_mission() which starts as integrity_error |
| 2.7 | Evidence integrity | Reads evidence through EvidenceStore.list(); never writes |
| 2.8 | Provider unavailable is resumable | Shows status, does not force state change |
| 2.9 | Adaptive states rejected | Adaptive Runtime is read-only from Control Plane |
| 2.10 | SDK compatibility inline | Uses inspect_mission which provides all SDK fields |

### Verdict: **PASS** ✅

---

## Gate 3: Security Boundary

### Question
Does the Control Plane maintain security isolation from the Runtime?

### Check Items

| # | Check | Evidence |
|---|-------|----------|
| 3.1 | No direct DB access | Control Plane uses HTTP API only |
| 3.2 | No filesystem access | No server-side code in Next.js |
| 3.3 | Authentication boundary defined? | Deferred: local-only project (see note) |
| 3.4 | CORS correctly scoped? | FastAPI default; tighten if exposed |
| 3.5 | No secrets in frontend code? | API URL only; no tokens/keys |
| 3.6 | Human approval gate intact? | NSEC Article 37 — approve_mission() requires human actor |
| 3.7 | No tool execution from UI? | Control Plane has no tool execution capability |

### Note on Authentication
NEXARA-PRIME is a **local-only private project** (per project constitution). Authentication is not required for V1. If the Control Plane is ever exposed beyond localhost, authentication must be added as a prerequisite gate.

### Verdict: **PASS** ✅

---

## Gate 4: UX Validation

### Question
Does the UI design meet Apple-level product quality standards?

### Check Items

| # | Check | Status |
|---|-------|--------|
| 4.1 | Design tokens defined (color, type, spacing)? | ✅ UI_COMPONENT_MAP.md |
| 4.2 | Every component has empty/loading/error states? | ✅ All 40+ components specified with states |
| 4.3 | Responsive breakpoints defined? | ✅ 4 breakpoints (1280/1024/768/<768) |
| 4.4 | Motion design documented? | ✅ Duration/easing for 10 interaction types |
| 4.5 | Accessibility baseline? | Semantic HTML, ARIA labels, keyboard navigation, focus-visible |
| 4.6 | No rejected aesthetics? | ✅ No AI-HUD, no robot avatars, no cyberpunk |
| 4.7 | User flows cover all key scenarios? | ✅ 6 flows (create, approve, execute, recover, audit, health) |

### Accessibility Minimum
- All interactive elements keyboard-accessible
- Focus visible on all focusable elements
- Color not the sole indicator of state (icons + text alongside badges)
- Semantic heading hierarchy (h1 → h2 → h3)
- `aria-label` on icon-only buttons
- Reduced motion media query respected

### Verdict: **PASS** ✅

---

## Gate 5: Production Readiness

### Question
Is the Control Plane ready for implementation with no blocking unknowns?

### Check Items

| # | Check | Status |
|---|-------|--------|
| 5.1 | Tech stack matches project? | ✅ Next.js 16, TypeScript strict, Tailwind v4, shadcn/ui, Lucide |
| 5.2 | No new dependencies beyond existing? | ✅ All listed in UI_COMPONENT_MAP.md (all in project) |
| 5.3 | API contract defined? | ✅ 26 endpoints mapped to UI needs |
| 5.4 | Information architecture complete? | ✅ 5 modules, fully specified |
| 5.5 | Component library scoped? | ✅ 40+ components with states |
| 5.6 | Integration path clear? | ✅ Static export mounted at /console (api.py:224) |
| 5.7 | Test strategy? | Component unit tests + E2E with Runtime mock |
| 5.8 | Build pipeline? | Next.js static export → `ui/out/` → served by FastAPI |
| 5.9 | Known limitations documented? | ✅ 2 known issues (REG-001 fixed, RECEIPT-ENV-001 environmental) |

### Build Pipeline
```
ui/ (Next.js 16 App Router)
  │
  ├── pnpm build (static export)
  │   → ui/out/
  │
  └── Mounted by FastAPI at /console
      (api.py:224 — already implemented)

Development:
  pnpm dev → localhost:3000
  FastAPI → localhost:8000
  → CORS proxy during dev
```

### Verdict: **PASS** ✅

---

## Gate Summary

| Gate | Status |
|------|--------|
| Gate 1: Architecture Alignment | ✅ PASS |
| Gate 2: Runtime Contract Compliance | ✅ PASS |
| Gate 3: Security Boundary | ✅ PASS (with auth note) |
| Gate 4: UX Validation | ✅ PASS |
| Gate 5: Production Readiness | ✅ PASS |

---

## Pre-Implementation Checklist

Before writing any UI code:

- [ ] Human approval gate (NSEC Article 37) — explicit "proceed" signal
- [ ] Runtime API extended (5 EXTEND + 1 NEW endpoint) — or plan to implement alongside UI
- [ ] Development environment: `pnpm install` in `ui/`
- [ ] FastAPI CORS configured for `localhost:3000` during dev
- [ ] Existing UI assets in `ui/out/` backed up

---

## Post-Implementation Verification

After UI implementation:

- [ ] Full test suite re-run: 2044/2044 must remain PASS
- [ ] No new Python test failures
- [ ] UI builds without errors (`pnpm build`)
- [ ] UI mounts correctly at `/console`
- [ ] All 6 user flows functional
- [ ] All components handle empty/loading/error states
- [ ] Accessibility audit passes (axe DevTools)
- [ ] Design QA against UI_COMPONENT_MAP.md tokens
- [ ] NSEC compliance verification
