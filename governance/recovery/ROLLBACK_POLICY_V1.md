# NEXARA PRIME — Rollback Policy V1

> **Program:** NEXARA_FIRST_PARTY_SOVEREIGN_AGENT
> **Platform:** NEXARA_PRIME
> **Version:** 1.0.0
> **Python:** 3.12.13 | **Swift:** 6.3.3 | **Xcode:** 26.6

## Purpose

Define the classification, procedures, and recovery paths for failures
encountered during development, CI, release, or deployment. Every failure
must be classified, logged, and resolved according to the procedures in
this document.

## Failure Classification

### Failure Classes

| Class         | Code        | Description                                      | Severity |
|---------------|-------------|--------------------------------------------------|----------|
| Transient     | TRANSIENT   | Intermittent failure (network, timeout, resource) | LOW      |
| Dependency    | DEPENDENCY  | External service, package, or API failure         | MEDIUM   |
| Build         | BUILD       | Compilation or packaging error                    | HIGH     |
| Test          | TEST        | Test assertion failure or regression              | MEDIUM   |
| State Drift   | STATE_DRIFT | `.nexara/` state files inconsistent with reality  | HIGH     |
| Security      | SECURITY    | Secret leakage, permission bypass, audit failure  | CRITICAL |
| Configuration | CONFIG      | Invalid or missing configuration                  | HIGH     |
| Schema        | SCHEMA      | Contract schema violation (JSON, YAML, proto)    | HIGH     |
| Rollback      | ROLLBACK    | Failure during the rollback procedure itself      | CRITICAL |
| Unknown       | UNKNOWN     | Unclassified failure requiring investigation     | HIGH     |

### Severity Definitions

| Severity | Response Time | Resolution Time | Escalation |
|----------|---------------|-----------------|------------|
| LOW      | Next business day | 1 week | None |
| MEDIUM   | 4 hours       | 24 hours        | Senior contributor |
| HIGH     | 1 hour        | 4 hours         | Maintainer |
| CRITICAL | Immediate     | 1 hour          | Program lead + security lead |

## Recovery Procedures

### TRANSIENT — Retry with Backoff

```
1. Classify failure source (network call, resource lock, timeout)
2. Wait 30 seconds
3. Retry up to 3 times with exponential backoff (30s, 60s, 120s)
4. If still failing: escalate to DEPENDENCY or UNKNOWN
5. Log in .nexara/DECISION_LOG.md
```

### DEPENDENCY — Pin or Fall Back

```
1. Identify the failing dependency and version
2. Check dependency status page / service health
3. If transient: follow TRANSIENT procedure
4. If permanently broken:
   a. Pin to last known-good version
   b. File issue against dependency maintainer
   c. Evaluate alternative dependency
5. Update dependency lockfile
6. Log in .nexara/DECISION_LOG.md with affected version range
```

### BUILD — Fix and Rebuild

```
1. Capture full build log
2. Identify compilation error:
   a. Source code error → fix and commit
   b. Dependency version mismatch → roll dependency (see DEPENDENCY)
   c. Toolchain issue → verify toolchain version (Python 3.12.13, Swift 6.3.3, Xcode 26.6)
   d. Environment issue → clean build directory and rebuild
3. Increment build number
4. Rebuild and re-verify
5. Log in .nexara/DECISION_LOG.md with root cause
```

### TEST — Investigate Regression

```
1. Identify the failing test(s):
   a. Run the failing test in isolation: `pytest tests/path/to/test.py -x -v`
   b. Check if the test was already failing before the change (baseline comparison)
2. Classification:
   a. Legitimate regression → fix implementation
   b. Flaky test → quarantine and fix test
   c. Test environment issue → fix environment and re-run
   d. Baseline mismatch → update baseline if intentional change
3. Never disable a test without logging the reason in .nexara/DECISION_LOG.md
4. Log in .nexara/DECISION_LOG.md with test name, expected vs actual, and root cause
```

### STATE_DRIFT — Align State Files with Reality

```
1. Run: python3 scripts/governance/detect_state_drift.py
2. Review the detected inconsistencies:
   a. If GATE_STATUS.json is stale → update it to match actual gate progress
   b. If PROGRAM_STATE.json is stale → update it to match current state
   c. If git HEAD differs from recorded baseline → update BASELINE.json
   d. If working tree is dirty → commit or stash pending changes
3. Verify mutual consistency: both files must agree on:
   - current_program_gate
   - gate_status
   - gates_pass list
   - external_distribution status
4. Log the drift event and correction in .nexara/DECISION_LOG.md
```

### SECURITY — Immediate Lockdown

```
1. STOP all operations
2. Identify the compromised surface:
   a. Secret leakage → rotate all exposed credentials immediately
   b. Permission bypass → audit and fix permission model
   c. Audit chain break → investigate and restore audit integrity
3. Notify program lead and security lead immediately
4. Apply fix with highest priority
5. Post-incident review within 24 hours
6. Log in .nexara/DECISION_LOG.md with full incident report
   CRITICAL: Do not include the actual secret values in logs
```

### CONFIG — Validate and Correct

```
1. Identify the invalid or missing configuration:
   a. Missing env var → check .env.example and documentation
   b. Invalid YAML/JSON → run schema validation
   c. Wrong path or reference → correct to match filesystem
2. Apply correction
3. Re-run dependent operation
4. Log in .nexara/DECISION_LOG.md with the misconfiguration
```

### SCHEMA — Update Contract or Data

```
1. Identify which schema is violated (JSON, YAML, protobuf)
2. Determine root cause:
   a. Data is valid but schema is outdated → update schema
   b. Schema is correct but data is invalid → fix data generator
   c. Both are valid but incompatible → coordinate schema + data migration
3. Apply fix
4. Re-validate: python3 -c "import json, yaml; ..."
5. Log in .nexara/DECISION_LOG.md with schema version and migration details
```

### ROLLBACK (Rollback-of-Rollback) — Emergency Recovery

```
1. If the rollback itself fails:
   a. The system is in an undefined state → do not proceed
   b. Freeze all operations
   c. Escalate immediately to program lead + maintainer
2. Restoration options:
   a. Restore from git: git checkout <last-known-good-sha>
   b. Restore .nexara state from baseline: governance/baselines/<version>/
   c. Rebuild from clean checkout
3. Declare incident and initiate post-mortem
4. Log full details in .nexara/DECISION_LOG.md
```

## Rollback Decision Matrix

| Scenario | Action | Approval | Documentation |
|----------|--------|----------|---------------|
| CI pipeline failure (R0–R1) | Fix forward | None | Commit message |
| CI pipeline failure (R2+) | Fix forward or revert | Author +1 | PR description |
| Test regression (single test) | Fix forward | None | Commit message + test update |
| Test regression (broad) | Revert commit | Senior contributor | .nexara/DECISION_LOG.md |
| Build failure after merge | Fix forward | Author | Commit message |
| State drift detected | Run detect_state_drift.py | None | .nexara/DECISION_LOG.md |
| Security incident | Immediate revert + lockdown | Program lead | Incident report + DECISION_LOG.md |
| Production outage | Revert to last-known-good | Release manager | Incident report + DECISION_LOG.md |
| Failed rollback (ROLLBACK class) | Escalate to program lead | Program lead | Full incident report |

## Rollback Commands Reference

```bash
# Revert a single commit
git revert <SHA> --no-edit

# Revert a range of commits
git revert <OLDEST_SHA>^..<NEWEST_SHA>

# Reset to a known-good state (local only — use with extreme caution)
git reset --hard <KNOWN_GOOD_SHA>

# Restore .nexara state from a baseline snapshot
cp -r governance/baselines/<VERSION>/.nexara/* .nexara/

# Rebuild from clean state
rm -rf .venv dist .build
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Logging Requirements

Every rollback or recovery action MUST be logged in `.nexara/DECISION_LOG.md`
with the following format:

```markdown
## Rollback: <DATE> — <BRIEF TITLE>

- **Failure Class:** <CLASS_CODE>
- **Severity:** <LOW|MEDIUM|HIGH|CRITICAL>
- **Affected Commit:** <SHA>
- **Rollback Action:** <description of what was done>
- **Result:** <SUCCESS|PARTIAL|FAILED>
- **Escalated To:** <name(s)>
- **Follow-Up:** <any remaining action items>
- **Logged By:** <name>
```

## Prevention

To minimise the need for rollbacks:

1. Run `scripts/governance/detect_state_drift.py` before every merge
2. Ensure all CI layers pass before merging (see `.github/workflows/ci.yml`)
3. Validate merge contracts before merging (see `scripts/ci/validate_merge_contract.py`)
4. Freeze program baselines at each gate transition
5. Keep `.nexara/` state files updated immediately after each gate action
