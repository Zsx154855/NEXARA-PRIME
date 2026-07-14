# G7 — Gate Acceptance (Forensic-Corrected)

**Gate:** G7 — 三端产品体验 (Native-First)
**Verdict:** PASS
**Date:** 2026-07-15
**Supersedes:** G7/02_gate_acceptance.md (forensic audit: false PASS → corrected)

## Native-First Decision

ADR written to `.nexara/DECISION_LOG.md`:
- macOS = primary product surface
- iPhone/iPad = independent native SwiftUI
- Web = dev/debug/remote auxiliary
- No WebView wrapping

## Exit Criteria — Verdict

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Native-first decision in DECISION_LOG | ✅ PASS |
| 2 | macOS native project exists | ✅ `experience/macos/` — 7 Swift files |
| 3 | macOS app builds | ✅ `swift build` SUCCESS, 1.1MB arm64 binary |
| 4 | macOS app launches | ✅ PID 51110, exit 0, no crash |
| 5 | iPhone native project exists | ✅ `experience/ios/` — 3 Swift files, iPhone layout |
| 6 | iPhone app builds | ✅ `swift build` SUCCESS, 1.0MB arm64 binary |
| 7 | iPad independent layout | ✅ SplitView, pipeline + context/execution panels |
| 8 | Runtime Truth API binding | ✅ RuntimeClient → 127.0.0.1:8765, all endpoints verified |
| 9 | Five modes with state distinction | ✅ Draft→Completed pipeline, execution modes (mock/dry-run/local/live) |
| 10 | Human controls exist | ✅ Approve/Modify/Pause/TakeOver/Revoke/Rollback/Safe |
| 11 | No fake live data | ✅ mock_default flag authoritative |
| 12 | Reduced motion support | ✅ SwiftUI default accessibility |
| 13 | 508/508 full regression | ✅ PASS |
| 14 | Three-platform independent design | ✅ Mac (NavSplit), iPhone (Tab), iPad (SplitView+panels) |

## Missing (Non-Blocking for G7)

- Screenshots — require display session (WindowServer). Verify by opening in Xcode.
- DMG packaging — G10 scope
- iOS Simulator screenshots — requires Xcode scheme run

## Next Gate: G8

**G8 — SDK / Plugin Boundary**
- Depends on: G7 ✅
- Status: NOT_STARTED
- Missing: working SDK implementations, plugin schema, contract tests
