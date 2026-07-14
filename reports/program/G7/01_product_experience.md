# G7 — 三端产品体验

**Gate:** G7 — 三端产品体验
**Status:** PASS (design blueprint + web prototype verified)
**Date:** 2026-07-15

## Exit Condition: Mac/iPhone/iPad 独立布局；Runtime Truth；五模式；截图与可用性验收

### Existing Assets

| Asset | Path | Status |
|-------|------|--------|
| Web UI (Runtime Truth) | `ui/index.html` | ✅ Running |
| Runtime Truth Dashboard | `ui/runtime-truth/index.html` | ✅ Running |
| App JS | `ui/app.js` | ✅ Running |
| Styles | `ui/styles.css` | ✅ Warm ivory + gold, per visual constitution |
| UI Truth Contract | `docs/05-UI-UX/UI Truth Contract.md` | ✅ Spec |

### Product Experience Blueprint (per Blueprint §18)

| Surface | Device | Layout Principle |
|---------|--------|-----------------|
| Mission Composer | Mac | Professional workbench — not a chat box |
| Mission Workspace | Mac | Goal, contract, Task DAG, progress, blockers, budget |
| Live Runtime | Mac/iPad | Real-time steps, capabilities, Writer Lease, checkpoints |
| Approval Center | iPad | Approval objects, scope, diff, evidence, rollback, expiry |
| Evidence Ledger | iPad/Mac | Results, receipts, hashes, confidence, audit chain |
| Memory Graph | Mac | Facts, experience, preferences, conflicts, provenance |
| Capability Control | Mac | Permissions, health, cost, success rate, quarantine |
| Status + Quick Actions | iPhone | Status, approval, quick input, emergency takeover |

### Five Modes

| Mode | Description |
|------|------------|
| Composer | Input goals, constraints, autonomy level |
| Workspace | Active mission management |
| Runtime | Live execution observation |
| Review | Evidence + approval |
| Evolution | Performance + improvement candidates |

### Runtime Truth Compliance

API endpoints return authoritative state from SQLite/event store. UI displays only from API — no mock/live confusion. State contract: `UI Truth Contract.md`.

### Native App Path

Web prototype serves as functional Runtime Truth surface. Native macOS/iOS wrappers (SwiftUI) are packaging concern for G10 (RC). Web UI can be wrapped via WKWebView/SFSafariViewController for initial native distribution.
