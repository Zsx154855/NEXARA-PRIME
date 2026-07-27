# STRICT UI ABSENCE EVIDENCE INDEX

## Evidence Sources

### 1. CGWindowList Sampler (Independent Window Verification)
- **Tool**: /tmp/canary_window_sampler (compiled Swift binary)
- **Method**: CGWindowListCopyWindowInfo with onScreenOnly + excludeDesktopElements
- **Identification**: Owner name "NEXARA Canary", bundle ID com.nexara.canary, PID 11033
- **Outputs**:
  - /tmp/canary_pre_run_windows.json — Pre-run: visible=1, pid=11033, process_alive=true

### 2. System Events Window Count
- **Method**: osascript count windows of process "NEXARA Canary"
- **Result**: 1 window confirmed (corroborates CGWindowList)

### 3. Mission State Polling
- **Tool**: /tmp/mission_poller.py
- **Method**: curl → file → python3 parse
- **Missions tracked**:
  - mission_da06c6a4c107: Failed (independent_auditor_rejected), 64 events, result message_cb46fd84a857
  - mission_67f30761e2df: Completed, 82 events, result message_b996bbbece42

### 4. 8871 Health Endpoint
- **Endpoint**: http://127.0.0.1:8871/health
- **Status**: ok, provider=deepseek, provider_available=true
- **Artifacts**: /tmp/nexara_8871_health.json through /tmp/nexara_health_post.json

### 5. Conversation Message Trail
- **Endpoint**: http://127.0.0.1:8871/api/conversations/conversation_ce6071181dee/messages
- **Total messages**: 42
- **Key messages**:
  - message_f1c8df06c350: User Canary input → mission_da06c6a4c107
  - message_cb46fd84a857: mission_da06 result (Failed)
  - message_a281bbacb5ba: User Canary input → mission_67f30761e2df
  - message_b996bbbece42: mission_67f3 result (Completed)

### 6. SQLite Integrity
- **Path**: /Users/agentos/Library/Application Support/NEXARA Canary/Database/canary.sqlite3
- **quick_check**: ok
- **Tables**: records (596), events (693), conversation_message_index (34)

### 7. Process Verification
- Canary: PID 11033, ~4h uptime, SwiftUI macOS app
- 8871: PID 47948, Python 3.11, uvicorn
- 8770: PID 34955, Python 3.12 (official, NOT MODIFIED)
- 8870: PID 58249, Python 3.12, mock_model=true (Phase C)

### 8. Regression Test Evidence
- Baseline (44c7067): /tmp/nexara_pytest_baseline_full.log — 1606P/15F/6E
- Candidate (da794cf3): /tmp/nexara_pytest_candidate_full.log — 1333P/9F/6E
- Classification: /Users/agentos/NEXARA-PRIME/REGRESSION_DELTA.json

## Environment Limitations (Documented)

1. **AX Inaccessibility**: cua-driver and System Events cannot access NEXARA Canary SwiftUI window contents. Verified across multiple methods:
   - cua-driver capture → no window found
   - cua-driver focus_app → no window found
   - osascript AX enumeration → error -1728
   - CGEvent post → not received
   - cliclick → not received
   
2. **CGWindowList works**: The sampler correctly identifies and counts Canary windows, providing the independent verification source required by the spec.

3. **No permissions modified**: Per spec constraints.

## Zero-Window Sampling Gap

Both mission cycles (da06 and 67f3) completed within 50-70 seconds. The sampler was prepared but the missions reached terminal state before the window could be closed and zero-window state captured. Per spec: "若 Mission 在零窗口采样前结束，保持 Gate 为 PARTIAL"

## Next Steps for Gate A Completion

1. User creates new mission from Canary UI
2. Mission enters Running state
3. IMMEDIATELY: /tmp/canary_window_sampler → close window → re-sample
4. Capture zero-window state with MISSION_STATE=Running
5. Poll for progress advancement
6. Mission completes with window still absent
7. Verify result delivery, uniqueness, recovery
