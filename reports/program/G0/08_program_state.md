# 08 — Program State

**G0 Reality Inventory V2 | 2026-07-23 | HEAD dd0505a**

基于 `.nexara/` 程序状态文件 + Forensic Audit + 代码实际状态的整合程序状态快照。

---

## 8.1 Program Identity

| Field | Value |
|-------|-------|
| Program | NEXARA_FIRST_PARTY_SOVEREIGN_AGENT |
| Platform | NEXARA PRIME |
| Agent Package | nexara_prime.agent |
| Hermes Runtime Dependency | 0 ✅ |
| Repository | /Users/agentos/NEXARA-PRIME |
| Remote | https://github.com/Zsx154855/NEXARA-PRIME.git |
| Branch | main |
| HEAD | dd0505ac53721d8e2e6150e47936119fe16734d6 |
| Python | 3.12.13 |
| License | MIT |

---

## 8.2 Runtime Metrics

| Metric | Value |
|--------|-------|
| Test Baseline | 682 passed, 0 failed |
| Test Files | 27 |
| Test LOC | 13,076 |
| Source Modules | 65+ .py files |
| Source LOC | ~20,000 |
| Rust/Ruff Lint | Clean |
| Secret Scan | CLEAN (0 findings) |
| TypeScript Build | PASS |
| Swift macOS Build | PASS (dist binary exists) |
| Swift iOS Build | PASS (no binary artifact) |
| CI Status | CI_PLATFORM_FAILURE (no runner allocated) |

---

## 8.3 Gate Truth (Corrected)

```json
{
  "program": "NEXARA_FIRST_PARTY_SOVEREIGN_AGENT",
  "inventory_date": "2026-07-23",
  "baseline_head": "dd0505ac53721d8e2e6150e47936119fe16734d6",
  "gates": [
    {"id": "G0", "status": "PASS", "verified": true},
    {"id": "G1", "status": "PASS", "verified": true},
    {"id": "G2", "status": "PASS", "verified": true},
    {"id": "G3", "status": "PASS", "verified": true},
    {"id": "G4", "status": "PASS", "verified": true},
    {"id": "G5", "status": "PASS", "verified": true},
    {"id": "G6", "status": "PASS", "verified": true},
    {"id": "G7", "status": "PARTIAL", "verified": true,
      "missing": ["macOS native screenshots", "iOS native screenshots", "iPad layout", "usability acceptance"]},
    {"id": "G8", "status": "NOT_STARTED", "verified": true,
      "missing": ["installable SDK", "plugin schema", "signature verification"]},
    {"id": "G9", "status": "PARTIAL", "verified": true,
      "missing": ["benchmark execution evidence", "candidate comparison pipeline", "evolution E2E"]},
    {"id": "G10", "status": "BLOCKED", "verified": true,
      "blocked_by": ["macOS code signing certificate", "iOS Provisioning Profile"]}
  ],
  "earliest_incomplete_gate": "G7",
  "gates_verified_pass": 7,
  "gates_partial": 2,
  "gates_not_started": 1,
  "gates_blocked": 1,
  "previous_false_pass_claims": 4
}
```

---

## 8.4 Current System Maturity

基于 Blueprint §3 成熟度模型重新评估：

| Domain | Weight | V1 Score | Current Score | Delta |
|--------|--------|----------|---------------|-------|
| Runtime Kernel | 20 | 4.3/5 | 4.5/5 | +0.2 |
| 治理与安全 | 15 | 4.2/5 | 4.4/5 | +0.2 |
| Evidence/Memory/Recovery | 15 | 3.8/5 | 4.0/5 | +0.2 |
| Platform Services | 15 | 1.8/5 | 2.5/5 | +0.7 |
| 第一方 Agent Domain | 15 | 0.5/5 | 3.0/5 | +2.5 |
| 产品体验 | 7 | 1.0/5 | 2.0/5 | +1.0 |
| SDK/Plugin/Ecosystem | 3 | 0.5/5 | 0.8/5 | +0.3 |
| Provider/SecretStore | 10 | 4.1/5 | 4.3/5 | +0.2 |

**加权总分: 3.3/5 (66%)** — 较 Blueprint 编写时的 2.9/5 (58%) 提升 8pp。

最大提升来自第一方 Agent Domain (+2.5) 和 Platform Services (+0.7)。

---

## 8.5 Active Blockers

| Blocker | Type | Severity | Mitigation |
|---------|------|----------|------------|
| macOS Code Signing Certificate | External | BLOCKING G10 | Apple Developer Program ($99/yr) |
| macOS Notarization | External | BLOCKING G10 | Requires signing cert |
| iOS Provisioning Profile | External | BLOCKING G10 | Apple Developer Program |
| Product Brand Name | Decision | BLOCKING G10 | Human decision required |
| CI Runner Unavailable | Infrastructure | HIGH | Self-hosted runner setup |
| AOS Source Files Missing | Technical | CRITICAL | Recovery or rebuild |
| GATE_STATUS.json Stale | Process | HIGH | Overwrite with truth |

---

## 8.6 Branch Model

| Branch | Purpose | Status |
|--------|---------|--------|
| main | Default/Release | ✅ Current |
| work/nexara-adaptive-runtime-v1 | Historical program baseline | 📦 Archived |
| work/nexara-post-baseline-v1 | Previous development | 📦 Archived |
| work/nexara-autonomous-runtime-orchestration-v1 | Orchestration PR #8 | ✅ Merged |

---

## 8.7 Recent Merged PRs

| PR | Title | Status |
|----|-------|--------|
| #5 | feat: program state consolidation baseline | MERGED (squash) |
| #8 | feat(orchestration): autonomous runtime orchestration | MERGED (squash) |
| #10 | fix: review consistency repair | MERGED (squash) |
| #16 | refactor(convergence): unify capability registry, token compiler, scheduler | MERGED |
| #18 | refactor(runtime): converge NexaraRuntime authority (v2 clean) | MERGED |
| #21 | feat(runtime): close real provider context audit loop | MERGED |
| #22 | fix(governance): isolate worktree execution spaces from NSEC scans | MERGED (HEAD) |

---

## 8.8 Program Health Indicators

| Indicator | Status |
|-----------|--------|
| Test Suite | 🟢 682/682 GREEN |
| Secret Hygiene | 🟢 CLEAN |
| Security Audit | 🟢 0 bypass, 0 leakage, 0 escape |
| Code Quality | 🟢 ruff clean |
| Type Safety | 🟢 TypeScript PASS |
| Documentation | 🟢 54 .md files, 7 ADRs |
| CI Pipeline | 🔴 Runner unavailable |
| Gate Truth | 🔴 4 false PASS claims |
| Source Integrity | 🔴 13 AOS modules .pyc only |
| Release Readiness | 🟡 LOCAL_READY, DIST_BLOCKED |

---

## 8.9 Human Decisions Pending

1. **Product Brand Name** — "NEXARA Sovereign Agent" 是内部代号
2. **Apple Developer Program** — 是否购买用于代码签名
3. **git push to remote** — 暂不推送
4. **G8 SDK Strategy** — 优先完成哪个 SDK (推荐 Python)
5. **AOS Recovery Strategy** — 恢复源文件 vs 从 runtime 重建
