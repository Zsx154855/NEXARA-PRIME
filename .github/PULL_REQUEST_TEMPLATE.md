---
name: Merge Contract
about: Formal merge request with governance gate tracking.
title: ''
labels: ''
assignees: ''
---

<!--
  NEXARA PRIME Merge Contract — do not merge until all required fields are
  filled and pre-merge verification is complete.
-->

## Merge Contract

| Field | Value |
|-------|-------|
| **mission_id** | <!-- e.g. MISSION-2026-007 --> |
| **program_id** | <!-- e.g. NEXARA_FIRST_PARTY_SOVEREIGN_AGENT --> |
| **gate_scope** | <!-- The gates this change touches, e.g. G7, G8, G10 --> |
| **risk_level** | <!-- R0 / R1 / R2 / R3 / R4 --> |
| **changed_modules** | <!-- Comma-separated list of affected modules/packages --> |
| **test_summary** | <!-- Summary of test results, coverage delta --> |
| **evidence_refs** | <!-- Links or paths to evidence files in reports/ --> |
| **rollback_plan** | <!-- How to revert if this merge causes issues --> |
| **external_dependencies** | <!-- Any external services, API keys, certs required --> |

## Pre-Merge Verification

- [ ] All CI checks pass (Python + TypeScript + Swift + Governance)
- [ ] Tests pass at baseline level (517+ passed, 0 failed)
- [ ] Secret scan passes (no hardcoded credentials)
- [ ] State drift check passes (.nexara JSON consistent with git HEAD)
- [ ] Merge contract fields above are all filled (no blank values)
- [ ] Risk level matches the gate policy (R0–R1 auto-merge, R2+ requires approval)
- [ ] Rollback plan is realistic and actionable
- [ ] Evidence references point to valid files
- [ ] CHANGELOG or commit history accurately reflects changes

## Release Gate Override (if applicable)

- [ ] This is an emergency hotfix (requires explicit approval for R2+)
- [ ] Release approval matrix overrides have been logged
