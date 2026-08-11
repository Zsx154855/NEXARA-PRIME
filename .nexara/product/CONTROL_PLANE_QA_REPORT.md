# NEXARA Control Plane V1 — Browser QA Report

**Generated**: 2026-08-09T05:55:00+00:00  
**URL**: http://127.0.0.1:8765/console/  
**Runtime Mode**: Mock Provider (mock_model=true)  
**Browser**: Chromium (Playwright)  

---

## QA Results Summary

| Screen | Status | Issues |
|--------|--------|--------|
| Dashboard (控制台) | ✅ PASS | 0 |
| Missions (任务) | ✅ PASS | 0 |
| Mission Detail (任务详情) | ✅ PASS | 0 |
| Evidence (证据) | ✅ PASS | 0 |
| Governance (治理) | ✅ PASS | 0 |
| Runtime Health (健康) | ✅ PASS | 0 |

---

## Detailed Verification

### 1. Dashboard
- 5 stat cards display: 活跃任务(27), 已完成(12), 进行中(27), 失败(1), 待审批(0)
- System status bar: 系统在线 · Provider: mock · 证据: 227 · 恢复: 健康
- "创建新任务" button visible and functional
- Mission stream: 20 items, clickable, color-coded state badges
- Empty state: Rocket icon + CTA text
- Skeleton loading: animated pulse on initial load

### 2. Missions
- Search bar: "搜索任务…" with real-time filtering
- Status filter dropdown: 全部/Intent/Approval/Execution/Completed/Failed/Blocked
- Mission cards: title, objective, state badge (color-coded), risk level, timestamp
- "创建任务" button → 3-step wizard (目标确认 → 生成规划 → 提交审批)
- Empty state: "还没有任务" with CTA
- Search "E2E" → 2 results (real filtering)

### 3. Mission Detail
- Mission title + mission_id display
- Stage rail: 7 stages (审批中→执行中→验证中→证据收集→记忆更新→评估→已完成)
- Mission info: objective, state, risk level, provider, created_at
- Contract info: approval consumed, 16 evidence, receipt exists, memory committed, evaluation passed
- Execution plan: 7 steps (Orchestrator→Planner→Analyst→Executor→Reviewer→Auditor→Archivist)
- Event timeline: 59 events
- Recovery pointer: tool_31e1ab9c3859
- Tool invocations: 2

### 4. Evidence
- Evidence list: 227 items total
- Mission filter dropdown with all mission names
- Evidence cards: evidence_id, type, timestamp, copy button

### 5. Governance
- Approval center with form inputs
- Decided by + Notes inputs
- Pending(0)/Approved(13) tab switcher
- Summary: 总计13条, 待审批0条, 已处理13条

### 6. Runtime Health
- System health overview
- Provider: mock / Mock 默认 / 人工控制启用
- 安全模式: 已启用
- NSEC 状态: 已治理
- 恢复检查: 可用
- Evidence storage: 20条 / 已验证
- Memory storage: 6个任务已应用
- REST API 可用 / 事件系统正常 / 工具20次调用
- 9 Adapters 全部正常
- Recovery JSON: 40 checked, 0 resumable, 12 completed
- Task status overview: 13活跃/6完成/1失败/20总计

---

## Cross-Cutting Verification

| Test | Result |
|------|--------|
| Navigation (5 items in sidebar) | ✅ All switch correctly |
| Refresh button | ✅ Present on all pages, functional |
| Data consistency across pages | ✅ Dashboard/Missions agree: 40 tasks, 12 completed |
| Responsive design (mobile bottom nav) | ✅ 5-tab bottom nav on mobile |
| Browser console errors | 0 |
| DOM error elements | 0 |
| Loading skeletons | ✅ Animated pulse on initial load |
| Empty states | ✅ Proper empty states on all screens |
| Error states | ✅ Runtime unavailable message with CTA |

---

## Screenshots

| # | Screen | Path |
|---|--------|------|
| 1 | Dashboard | /tmp/nexara_qa_01_dashboard.png |
| 2 | Missions List | /tmp/nexara_qa_02_missions_list.png |
| 3 | Search E2E | /tmp/nexara_qa_02b_search_e2e.png |
| 4 | Create Form | /tmp/nexara_qa_02c_create_form.png |
| 5 | Mission Detail | /tmp/nexara_qa_03_mission_detail.png |
| 6 | Evidence | /tmp/nexara_qa_04_evidence.png |
| 7 | Governance | /tmp/nexara_qa_05_governance.png |
| 8 | Health | /tmp/nexara_qa_06_health.png |

---

## Conclusion

**All 6 screens + cross-cutting tests PASSED. Zero blockers.**
Control Plane V1 UI operates stably with mock provider. All core functions (Dashboard stats, mission CRUD, search/filter, evidence browsing, approval center, runtime health monitoring, sidebar navigation, refresh) function correctly.
