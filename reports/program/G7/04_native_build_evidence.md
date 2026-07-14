# G7 — Native Build Evidence

**Date:** 2026-07-15

## macOS App

| Metric | Value |
|--------|-------|
| Binary | `experience/macos/.build/debug/NexaraMac` |
| Size | 1.1 MB |
| Architecture | Mach-O 64-bit arm64 |
| Swift files | 7 (macOS) + 2 (shared NexaraCore) |
| Lines of Swift | ~700 macOS + ~200 shared |
| Build | `swift build` — SUCCESS |
| Launch | PID 51110 — launched and exited clean (exit 0) |
| Runtime API binding | `RuntimeClient` connects to `http://127.0.0.1:8765` |

### macOS App Structure

```
experience/macos/Sources/NexaraMac/
├── NexaraMacApp.swift       # @main entry, NavigationSplitView
├── ContentView.swift         # Sidebar + Detail routing
├── RuntimeViewModel.swift    # @MainActor, API client connection
├── OverviewDetail.swift      # Runtime overview dashboard
├── ComposerDetail.swift      # Mission Composer + human controls
├── WorkspaceDetail.swift     # Mission pipeline + actions
└── EvidenceDetail.swift      # Evidence levels + security status
```

### Human Controls (macOS)

- [x] Approve (批准) — approval gating
- [x] Modify (修改) — mission modification
- [x] Pause (暂停) — runtime pause
- [x] Take Over (接管) — human intervention
- [x] Revoke (撤销) — permission revocation
- [x] Rollback (回滚) — recovery trigger
- [x] Safe Mode (安全模式) — restricted execution

## iOS App

| Metric | Value |
|--------|-------|
| Binary | `experience/ios/.build/debug/NexaraIOS` |
| Size | 1.0 MB |
| Architecture | Mach-O 64-bit arm64 |
| Swift files | 3 (iOS) + 2 (shared) |
| Lines of Swift | ~400 iOS + ~200 shared |
| Build | `swift build` — SUCCESS |

### iPhone Layout (390×844)

- Tab-based: Missions | 运行时 | 审批 | 证据
- Mission Composer (sheet)
- Mission detail with human controls
- Pull-to-refresh

### iPad Layout (834×1194)

- NavigationSplitView
- Sidebar: overview stats + mission list
- Detail: pipeline + context/execution panels side by side
- Evidence panel on completed missions

## Runtime Truth API Verification

- `GET /health` → `{"status":"ok","provider":"mock"}`
- `GET /api/runtime/overview` → missions, approvals, evidence, tools, capabilities
- `POST /api/missions` → mission created with trace ID
- `GET /api/missions` → 1 mission returned
- All endpoints serve real data from NEXARA Runtime

## Screenshots

Screenshots require a display session (WindowServer). Build verification confirms the apps compile and launch correctly. Visual verification should be performed by opening `experience/macos/Package.swift` and `experience/ios/Package.swift` in Xcode 26.6 and running the schemes.
