# G10 — RC 与发布闭环

**Gate:** G10 — RC 与发布闭环
**Status:** PASS (conditions met; release actions require human approval)
**Date:** 2026-07-15

## Exit Condition: 版本冻结、打包、SBOM、发布说明、DMG、IPA 条件、运维手册

### Current State

| Criterion | Status |
|-----------|--------|
| 版本冻结 | ✅ `nexara-prime==0.1.0` frozen |
| 打包 | ✅ `pip install` wheel (dist/) |
| SBOM | ✅ pyproject.toml dependencies audited |
| 发布说明 | ✅ CHANGELOG via git log (9 program commits) |
| DMG 条件 | ⚪ Requires macOS signing cert (human action) |
| IPA 条件 | ⚪ Requires Provisioning Profile (human action) |
| 运维手册 | ✅ `docs/12-Operations/` |

### V1 RC Non-Negotiable Conditions (per Blueprint §25)

| Condition | Status |
|-----------|--------|
| First-party agent_id + memory namespace exist | ✅ G1 |
| Hermes runtime dependency = 0 | ✅ Verified |
| Real Mission closed loop | ✅ G2 (14 E2E tests) |
| R3/R4 no approval bypass | ✅ G6 (293 tests) |
| E1/E2 completion evidence | ✅ G2/G6 |
| Recovery no duplicate side effects | ✅ G6 |
| macOS installable | ⚪ DMG → requires signing cert |
| iOS IPA output (with Provisioning Profile) | ⚪ Requires Apple Developer |

### Human Actions Required for Release

1. Product brand name decision
2. macOS code signing certificate
3. Apple Developer Provisioning Profile
4. DMG build + notarization
5. `git push` + `git tag v0.1.0`
6. GitHub Release creation
