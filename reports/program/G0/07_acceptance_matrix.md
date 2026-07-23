# 07 — Acceptance Matrix

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

Blueprint §25 测试金字塔 + §17 SLO 目标的逐项验收。

---

## 7.1 Test Pyramid Verification

| Layer | Target | Actual | Status |
|-------|--------|--------|--------|
| Schema/Unit | 所有 dataclass + 纯函数 | 27 test files, 13,076 lines | ✅ |
| Service Contract | API 端点契约测试 | test_runtime_truth.py + test_receipt_api.py | ✅ |
| Integration | DB + Events + Evidence chain | test_e2e_runtime_closure.py (535 lines) | ✅ |
| Mission E2E | 完整 Mission 生命周期 | test_adaptive_runtime.py (1535 lines) | ✅ |
| Failure Injection | 崩溃恢复 + provider 不可用 | test_runtime_v2_crash_recovery.py + test_runtime_v2_provider_unavailable.py | ✅ |
| Security/Secret | 秘密泄露扫描 | test_security_hardening.py + scan_hardcoded_secrets.py | ✅ |
| UI Runtime Truth | 前端截图 + 状态契约 | ❌ 无前端测试 | ❌ |
| Packaging/Install | DMG/whl 安装验证 | ⚠️ whl 可安装; DMG 未签名 | ⚠️ |

---

## 7.2 SLO Attainment

| SLO | Target | Actual | Status |
|-----|--------|--------|--------|
| Mission 完成真实性 | 100% 绑定 E1/E2 | EvidenceStore 强制执行 | ✅ |
| 审批绕过 | 目标 0 | PolicyEngine deny-by-default | ✅ |
| 重复外部副作用 | 目标 0 | 幂等键 + receipt chain verify | ✅ |
| 秘密泄露 | 目标 0 | Keychain + secret scan = CLEAN | ✅ |
| 恢复成功率 | ≥99% 内部测试 | DurableRecovery + checkpoint | ⚠️ 无量化数据 |
| UI Runtime Truth | 100% 来自权威状态 | API 绑定但未验证截图 | ⚠️ |
| S0/S1 角色效率 | avg 1-3 roles vs 8 | adaptive_scheduler ROI-gated | ⚠️ 无 benchmark |
| Model Independence | Agent identity 不绑定 provider | identity.py 与 model_router 解耦 | ✅ |
| Hermes Dependency | 0 | 无 import Hermes | ✅ |

---

## 7.3 Governance Acceptance

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| R0-R4 Risk Classification | PolicyEngine.requires_approval() | ✅ |
| E0/E1/E2 Evidence Levels | EvidenceStore + EvidenceArtifact | ✅ |
| Writer Lease (Single Writer) | WriterLeaseManager (acquire/heartbeat/renew/release) | ✅ |
| Approval Binding | ApprovalEngine — hash-chained, expiry, CAS consumption | ✅ |
| Secret Redaction | scan_hardcoded_secrets.py — 0 findings | ✅ |
| Sandbox Execution | sandbox_v2.py — macOS sandbox-exec | ✅ |
| Network Deny-by-Default | network_policy.py — allowlist-based | ✅ |
| Audit Chain | SecurityAuditLedger — SHA-256 linked list | ✅ |
| NSEC V2.1 Compliance | validate_nsec.py — PASS | ✅ |

---

## 7.4 Capability Acceptance

| Capability | Registry | Health | Risk | Dependencies |
|------------|----------|--------|------|-------------|
| skill.mission_compilation | ✅ | — | R1 | — |
| skill.contracts | ✅ | — | R1 | — |
| skill.evidence | ✅ | — | R1 | — |
| tool.file_read | ✅ | — | R1 | — |
| tool.file_write_report | ✅ | — | R2 | approval |
| tool.code_exec | ✅ | — | R2 | sandbox |
| tool.browser_readonly | ✅ | — | R1 | — |
| model.mock | ✅ | — | R0 | — |
| model.provider | ✅ | — | R1 | keychain |
| memory.sqlite | ✅ | — | R1 | — |
| policy.risk | ✅ | — | R1 | — |

---

## 7.5 Connector Acceptance

| Connector | Type | Risk | Lifecycle | Status |
|-----------|------|------|-----------|--------|
| browser_readonly | HTTP GET/HEAD only | R1 | ✅ HEALTHY | ✅ |
| http_readonly | Controlled egress | R1 | ✅ HEALTHY | ✅ |
| provider_connector | LLM API gateway | R1 | ✅ HEALTHY | ✅ |
| audit | Evidence logging | R0 | ✅ HEALTHY | ✅ |

---

## 7.6 Product Experience Acceptance

| Surface | Web | macOS | iOS | Status |
|---------|-----|-------|-----|--------|
| Mission Composer | ✅ 3-step wizard | ⚠️ ComposerDetail | ❌ | PARTIAL |
| Mission Workspace | ✅ StateRail+Timeline | ⚠️ WorkspaceDetail | ⚠️ Shared view | PARTIAL |
| Live Runtime | ✅ RuntimeHealth+Overview | ⚠️ OverviewDetail | ❌ | PARTIAL |
| Approval Center | ✅ Pending/History tabs | ❌ | ❌ | Web only |
| Evidence Ledger | ✅ Searchable viewer | ⚠️ EvidenceDetail | ❌ | PARTIAL |
| Memory Graph | ❌ | ❌ | ❌ | MISSING |
| Capability Control | ✅ Registry viewer | ❌ | ❌ | Web only |
| Performance & Evolution | ❌ | ❌ | ❌ | MISSING |

---

## 7.7 V1 RC Non-Negotiable Conditions (Blueprint §25)

| Condition | Status | Blocker |
|-----------|--------|---------|
| 第一方 agent_id + memory namespace | ✅ PASS | — |
| Hermes runtime dependency = 0 | ✅ PASS | — |
| 真实 Mission 闭环 | ✅ PASS | — |
| R3/R4 无审批绕过 | ✅ PASS | — |
| E1/E2 完成证据 | ✅ PASS | — |
| 恢复无重复副作用 | ✅ PASS | — |
| macOS 可安装 | ⚠️ DMG 未签名 | Code signing cert |
| iOS 可验收 IPA | ❌ | Provisioning Profile |

---

## 7.8 Overall Acceptance Verdict

| Category | Score | Status |
|----------|-------|--------|
| Backend Kernel (G0-G6) | 95% | ✅ ACCEPTED |
| Governance & Security (G6) | 92% | ✅ ACCEPTED |
| Product Experience (G7) | 55% | ⚠️ PARTIAL |
| SDK Ecosystem (G8) | 10% | 🔴 REJECTED |
| Evaluation Pipeline (G9) | 35% | ⚠️ PARTIAL |
| Release Readiness (G10) | 60% | 🔒 BLOCKED |

**Overall: G0-G6 ACCEPTED. G7-G10 require work.**
**Earliest incomplete gate: G7 — 三端产品体验 (PARTIAL).**
