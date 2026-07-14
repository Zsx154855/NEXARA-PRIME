# Baseline Acceptance Record — v0.1.0

## Repository Information

| Field       | Value                                |
|-------------|--------------------------------------|
| Repository  | Zsx154855/NEXARA-PRIME               |
| Commit      | 546edb8                              |
| Branch      | work/nexara-adaptive-runtime-v1      |
| Date        | 2026-07-14T20:52Z                    |

## Gate Status

| Gate  | Result               |
|-------|----------------------|
| G0    | PASS                 |
| G1    | PASS                 |
| G2    | PASS                 |
| G3    | PASS                 |
| G4    | PASS                 |
| G5    | PASS                 |
| G6    | PASS                 |
| G7    | PASS                 |
| G8    | PASS                 |
| G9    | PASS                 |
| G10   | LOCAL_RELEASE_READY  |

## Test Results

- **Total tests:** 517
- **Passed:** 517
- **Failed:** 0
- **Skipped:** 0

## Artifacts

| Artifact            | SHA256                                                               |
|---------------------|----------------------------------------------------------------------|
| NexaraPrime.dmg     | 17760066c936b345b67f5efdcb3754e2f170fcb18e87796105cfeb7fbb3c3585     |
| nexara_prime-source.zip | 622c606e37fb0d8df14a84db8997f76dd8df606096e7fb9153eac6c7688545c4 |
| nexara_prime-0.1.0-py3-none-any.whl | 24858845d0113a3032a260602a6ad094522247808b90d02a90daebfe8b25f4a6 |
| nexara_prime-0.1.0.tar.gz | PENDING                                                          |
| sbom-cyclonedx-1.5.json | PENDING                                                          |
| NexaraPrime.app binary | 015e94aebf4d27cf452055bee791e558ef543c0617b46925d07cdad24c32d18f |
| nexara_prime-0.1.0-cp312-cp312-macosx_26_0_arm64.whl | PENDING                          |

## DMG Verification

- **DMG SHA256:** 17760066c936b345b67f5efdcb3754e2f170fcb18e87796105cfeb7fbb3c3585
- **Mount verified:** Yes (hdiutil attach/detach confirmed)
- **App bundle integrity:** Confirmed (codesign -dv)

## SBOM

- **Format:** CycloneDX 1.5
- **Scope:** All runtime and build dependencies for macOS, Python, and TypeScript modules
- **Evidence tracked:** Yes — per-package provenance hashes and dependency tree

## Distribution Status

| Target               | Status                       |
|----------------------|------------------------------|
| Internal (local)     | RELEASED                     |
| External distribution| BLOCKED_EXTERNAL_CREDENTIAL  |

## Pending Human Approvals

- External distribution credential review
- Code signing certificate authorization
- Apple notarization approval
- iOS IPA provisioning profile
- Brand name legal clearance

## Sign-off

| Role              | Signature | Date                |
|-------------------|-----------|---------------------|
| Engineering Lead  | PENDING   | —                   |
| Security Officer  | PENDING   | —                   |
| Product Owner     | PENDING   | —                   |
