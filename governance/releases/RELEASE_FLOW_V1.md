# NEXARA PRIME — Release Flow State Machine V1

> **Program:** NEXARA_FIRST_PARTY_SOVEREIGN_AGENT
> **Platform:** NEXARA_PRIME
> **Python:** 3.12.13 | **Swift:** 6.3.3 | **Xcode:** 26.6
> **Version:** 1.0.0

## Overview

The release flow is a state machine with explicit transitions. Each state has
a set of mandatory gating criteria that must be satisfied before the next
state can be reached. The flow covers the lifecycle from an initial draft
release candidate through final release and archival.

```
DRAFT ──> CANDIDATE ──> VALIDATING ──> LOCAL_RELEASE_READY ──> SIGNING_PENDING
  │                                                              │
  └──[cancelled]─────────────────────────────────────────────────┤
                                                                  │
                                                                  v
                                                         NOTARIZATION_PENDING
                                                                  │
                                                                  v
                                                         APPROVAL_GATE
                                                                  │
                                                                  v
                                                         RELEASED
                                                                  │
                                                                  v
                                                         ARCHIVED
```

## State Definitions

### DRAFT

A release draft has been created but no artifacts have been built.

**Entry Criteria:**
- All program gates G0–G9 are marked PASS in `.nexara/GATE_STATUS.json`
- Current gate is G10 (RC and Release)
- Working tree is clean (no uncommitted changes)
- Branch is up to date with main / target branch

**Exit Criteria:**
- Version number chosen and recorded
- Release notes skeleton created
- Artifact list defined

---

### CANDIDATE

A release candidate (RC) has been assembled.

**Entry Criteria:**
- DRAFT state exited successfully
- Release version tagged (e.g., `v0.1.0-rc1`)

**Exit Criteria:**
- All target artifacts built successfully:
  - Python wheel (`dist/nexara_prime-<VERSION>-py3-none-any.whl`)
  - Python source tarball (`dist/nexara_prime-<VERSION>.tar.gz`)
  - macOS DMG (`dist/NexaraMac-<VERSION>-unsigned.dmg`)
  - macOS app bundle (`dist/NexaraMac.app`)
  - SBOM (`dist/sbom-<VERSION>.json`)
  - Checksums file (`dist/checksums-<VERSION>.txt`)
- SHA256 checksums computed and recorded

---

### VALIDATING

Full test suite and acceptance checks run against the candidate.

**Gating Criteria:**
1. **Full Test Suite:** `pytest tests/ -q` — minimum 517 passed, 0 failed
2. **CI Pipeline:** All four layers pass (Python, TypeScript, Swift, Governance)
3. **Secret Scan:** No hardcoded credentials detected
4. **State Drift Check:** `.nexara/GATE_STATUS.json` and `.nexara/PROGRAM_STATE.json` are mutually consistent with git HEAD
5. **Baseline Comparison:** Test results match or exceed the frozen baseline
6. **Artifact Integrity:** All expected artifacts exist with matching checksums
7. **Evidence Review:** All required evidence files exist in `reports/program/G10/`

**Exit Criteria:**
- All validations pass
- Evidence is recorded in `reports/program/G10/04_local_release_evidence.md`

---

### LOCAL_RELEASE_READY

All internal validations pass. The release is ready for local deployment.

**Characteristics:**
- Internal distribution possible (same machine, same network)
- External distribution is **BLOCKED** until signing and notarization complete
- Human approval is **PENDING** for:
  - `git push origin <release-branch>`
  - `git tag v<MAJOR.MINOR.PATCH>`

**Gating Criteria:**
- VALIDATING passed
- All artifacts signed with local developer certificate
- DMG launch-verified
- Release manifest generated (`reports/program/G10/05_artifact_manifest.json`)

**Exit Criteria:**
- Human approves the push and tag
- External credentials sourced (code signing certificate, notarization profile)

---

### SIGNING_PENDING

Artifacts are queued for code signing.

**Gating Criteria:**
- LOCAL_RELEASE_READY exited successfully
- Apple Developer Program membership active
- Code signing certificate available (Developer ID Application)
- macOS app bundle signed: `codesign --verify --deep --strict`
- Notarization credentials configured in environment

**Exit Criteria:**
- All binaries and bundles signed successfully
- Code signature verification passes

---

### NOTARIZATION_PENDING

Signed artifacts are queued for Apple notarization.

**Gating Criteria:**
- SIGNING_PENDING exited successfully
- `xcrun notarytool submit` run against each signed artifact
- Notarization result: `Accepted`
- Stapling applied: `xcrun stapler staple`

**Exit Criteria:**
- Notarization accepted for all artifacts
- Stapling verification passes

---

### APPROVAL_GATE

Final human approval before release.

**Gating Criteria:**

| Requirement | R0–R1 | R2 | R3 | R4 |
|-------------|-------|----|----|----|
| Senior contributor approval | — | 1 | — | — |
| Maintainer approval | — | — | 2 | — |
| Program lead approval | — | — | — | 3 incl. lead |
| Release manager sign-off | — | 1 | 1 | 1 |
| Security review (R3+) | — | — | required | required |

**Exit Criteria:**
- All required approvals collected (see RELEASE_APPROVAL_MATRIX_V1.yaml)
- Release notes finalized
- CHANGELOG updated

---

### RELEASED

The release is published.

**Gating Criteria:**
- APPROVAL_GATE exited successfully
- Git tag `v<MAJOR.MINOR.PATCH>` pushed to remote
- GitHub Release created with changelog and artifact attachments
- DMG and ZIP distributed to intended channels

**Exit Criteria:**
- Release published on GitHub
- SBOM archived alongside release
- Checksums published

---

### ARCHIVED (Terminal State)

The release is complete and archived.

**Actions:**
- Release branch merged and tagged
- `.nexara/PROGRAM_STATE.json` updated with release metadata
- Baseline snapshot frozen in `governance/baselines/v<MAJOR.MINOR.PATCH>/`
- Release evidence moved to long-term storage
- Release artifacts retained per retention policy

## State Transition Rules

1. **Forward only:** States progress only in the defined order. No skipping.
2. **Cancellation:** A release can be cancelled at any state before RELEASED.
   Cancelled releases return to DRAFT with a reason logged in `.nexara/DECISION_LOG.md`.
3. **Rollback:** If a released artifact is found defective, the recovery
   procedure follows `governance/recovery/ROLLBACK_POLICY_V1.md`.
4. **Parallel releases:** Only one active release flow is permitted at a time.
   The current release state is tracked in `.nexara/GATE_STATUS.json`.

## Current State (2026-07-15)

| Property | Value |
|----------|-------|
| Current Gate | G10 |
| Release State | LOCAL_RELEASE_READY |
| External Distribution | BLOCKED_EXTERNAL_CREDENTIAL |
| Git Push/Tag | PENDING_HUMAN_APPROVAL |
| Product Brand | PRODUCT_DECISION_PENDING |
| Blockers | macOS code signing certificate, notarization, iOS profile |
