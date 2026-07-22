# NEXARA Sovereign CI Authority Bridge Contract V1

**Contract ID**: `SOVEREIGN_CI_AUTHORITY_BRIDGE_CONTRACT_V1`
**Authority Context**: `nexara/sovereign-delivery`
**Governed By**: NSEC V2.1 §18, §28, §43-§45
**Status**: ACTIVE
**Effective**: 2026-07-22
**TARGET_HEAD**: `60f5eb625b7d316a09cdd52e937e4e088d7289a3`
**PR**: `Zsx154855/NEXARA-PRIME#21`

---

## 1. Authority Context

The NEXARA Sovereign CI Authority Bridge (`nexara/sovereign-delivery`) is the single authoritative commit-status context for NEXARA-PRIME delivery. It supersedes GitHub Actions as the decision-making authority for merge-readiness.

## 2. Exact HEAD Binding

All status publications are bound to precisely one verified commit SHA. Any HEAD change invalidates all prior statuses. No status may be published against an unverified SHA.

## 3. Status Semantics

| State | Meaning |
|-------|---------|
| `pending` | Sovereign validation is executing. |
| `success` | All mandatory sovereign gates, full tests, Evidence, and Receipt passed. |
| `failure` | Code, test, governance, evidence, receipt, or repository state failed. |
| `error` | Validation cannot complete — permissions, API failure, tool failure, HEAD drift, or unverifiable facts. |

## 4. GitHub Actions Positioning

GitHub Actions checks are retained as non-authoritative advisory signals. The GitHub Actions Billing Lock shall be recorded as:
- `external_observation = BLOCKED_EXTERNAL`
- `authority_effect = NON_BLOCKING`

G9 must report both facts; neither shall overwrite the other.

## 5. Final Decision Semantics

```
G9_EXTERNAL_OBSERVATION = BLOCKED_EXTERNAL
SOVEREIGN_AUTHORITY_DECISION = PASS
```

Both values preserved independently.

## 6. Status Publication Rules

1. Re-read PR HEAD before every publication.
2. HEAD change invalidates prior verification.
3. Never publish `success` against unverified SHA.
4. Never manually force `success`.
5. Never skip Evidence/Receipt.

## 7. Required Check Takeover

`main` branch shall only require `nexara/sovereign-delivery` as sovereign required check. Existing GitHub Actions checks remain visible as non-required advisory signals.

## 8. Rollback Contract

Before modifying branch protection or rulesets, a complete snapshot must be saved. Any partial failure triggers automatic restoration of original settings.

## 9. Authoritative Gates (A1–A11)

| Gate | Name | Mandatory |
|------|------|-----------|
| A1 | TARGET_HEAD — local HEAD == GitHub PR HEAD | YES |
| A2 | REPOSITORY — clean worktree, no unauthorized files | YES |
| A3 | GOVERNANCE — NSEC V2.1 PASS, Drift PASS | YES |
| A4 | CONTRACT — Authority Contract valid, context unique | YES |
| A5 | FULL_VALIDATION — full test matrix executed with real counts | YES |
| A6 | STATIC_AND_SECURITY — Ruff, Secret Scan, git diff --check | YES |
| A7 | EVIDENCE — Canonical Evidence Schema with target_head binding | YES |
| A8 | RECEIPT — Evidence hash, authority context, publisher identity | YES |
| A9 | EXTERNAL_OBSERVATION — Real GitHub API status read | YES |
| A10 | REVIEW — Unresolved review threads audited | YES |
| A11 | FINAL_AUTHORITY — All A1-A10 mandatory gates must pass | YES |
