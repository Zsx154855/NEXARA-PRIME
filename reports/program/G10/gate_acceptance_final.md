# G10 — RC 与发布闭环 Gate Acceptance (Final)

**Date:** 2026-07-23
**Gate:** G10
**Status:** BLOCKED → **BLOCKED_ACKNOWLEDGED**

---

## 10.1 Exit Condition

Blueprint G10: "版本冻结、打包、SBOM、发布说明、DMG、IPA 条件、运维手册"

## 10.2 Local Release Verification (COMPLETE)

| Artifact | Status | Detail |
|----------|--------|--------|
| Python Wheel | ✅ | `nexara_prime-0.1.0-py3-none-any.whl` (68KB, 45 files) |
| Source Tarball | ✅ | `nexara_prime-0.1.0.tar.gz` (109KB) |
| macOS DMG (unsigned) | ✅ | `NexaraMac-0.1.0-unsigned.dmg` (558KB) |
| macOS .app Bundle | ✅ | `NexaraMac.app` — Mach-O arm64, 1.1MB |
| SBOM | ✅ | `sbom-0.1.0.json` (v0.1.0) |
| Checksums | ✅ | `checksums-0.1.0.txt` (SHA-256, 4 artifacts) |
| Release Notes | ✅ | `reports/program/G10/01_rc_release.md` + `04_local_release_evidence.md` |
| Operational Runbook | ✅ | `governance/releases/RELEASE_FLOW_V1.md` (10-state machine) |

## 10.3 External Blockers (DOCUMENTED)

| Blocker | Type | Detail | Resolution Path |
|---------|------|--------|-----------------|
| macOS Code Signing Certificate | External | Apple Developer Program required | $99/yr Apple Developer membership |
| macOS Notarization | External | Requires signing certificate first | Apple notary service |
| iOS Provisioning Profile | External | Apple Developer Program required | Same membership as above |
| Product Brand Name | Decision | "NEXARA Sovereign Agent" is codename | Human decision pending |

## 10.4 Test Baseline

| Metric | Value |
|--------|-------|
| Full Suite | 917 passed, 1 failed (pre-existing) |
| Runtime Truth API | 24/24 passed |
| G9 Evolution | 9/9 passed |
| Secret Scan | CLEAN (0 findings) |
| Security Audit | 0 bypass, 0 leakage, 0 escape |

## 10.5 What CAN Be Released Now

- ✅ Python package (`nexara-prime==0.1.0`) — installable via wheel
- ✅ Source distribution — installable via `pip install nexara_prime-0.1.0.tar.gz`
- ✅ Local macOS .app — runs unsigned on developer machine
- ⚠️ macOS DMG — unsigned, requires user to bypass Gatekeeper
- ❌ Signed/notarized macOS DMG — blocked
- ❌ iOS IPA — blocked

## 10.6 Gate Verdict: BLOCKED_ACKNOWLEDGED

Local release artifacts complete and verified. External distribution blocked by Apple Developer Program credentials. Program is **LOCAL_RELEASE_READY**.

## 10.7 Next Action (Human)

1. Obtain Apple Developer Program membership ($99/year)
2. Generate macOS code signing certificate
3. Generate iOS Provisioning Profile
4. Decide product brand name
5. Then: sign DMG → notarize → generate IPA → tag v0.1.0 → push

**No automated action can resolve these blockers.**
