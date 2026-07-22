# NEXARA Delivery Controller Contract V1

**Contract ID**: `DELIVERY_CONTROLLER_CONTRACT_V1`
**Version**: 1.0.0
**Governed By**: NSEC V2.0 §43-§45 (Evidence, Receipt, Definition of Done)
**Status**: ACTIVE
**Effective**: 2026-07-22

---

## Purpose

The Delivery Controller ensures that no Feature, Mission, or PR enters GitHub without first passing a series of automated readiness gates. It is the last line of automated defense before human review.

## Delivery Gate States

| State | Meaning |
|-------|---------|
| `INIT` | Controller initialized, no checks run |
| `AUDITING` | Running environment and repo scans |
| `VERIFYING` | Running test suite and static checks |
| `EVIDENCE_FREEZE` | All evidence collected and hashed |
| `READY_FOR_COMMIT` | All gates passed, safe to commit |
| `READY_FOR_PR` | All gates passed, safe to open PR |
| `BLOCKED` | One or more gates failed |

## Gate Definitions

### G1: Environment Check
- Python 3.9+ available
- Required packages importable (pydantic, pytest)
- Virtual environment accessible
- Working directory is a valid git repo

### G2: Repository Check
- Git worktree is clean (no uncommitted changes)
- Branch is not `main` (delivery from feature branches only)
- `.nexara/PROJECT_STATE.json` exists and is valid JSON

### G3: Contract Check
- NSEC V2.0 file exists and is readable
- Authority index is consistent
- No NSEC drift detected
- MERGE_CONTRACT_V1 exists

### G4: Test Check
- Test suite runs without failures
- Test count meets baseline minimum (≥ 800)
- No skipped tests without documented reason

### G5: Evidence Check
- Evidence directory exists with ≥ 1 evidence files
- Evidence files are valid JSON
- Evidence SHAs are verifiable

### G6: Receipt Check
- Receipt exists for current HEAD
- Receipt SHA-256 matches content
- Receipt references valid evidence

### G7: CI Dependency Check
- Required CI scripts exist (scripts/ci/)
- Secret scan script is accessible
- Ruff config is present

### G8: Review Readiness Check
- No merge conflicts with target branch
- Commit messages follow convention
- File changes are within expected scope

## State Transitions

```
INIT → AUDITING → VERIFYING → EVIDENCE_FREEZE → READY_FOR_COMMIT → READY_FOR_PR
  ↓        ↓           ↓              ↓                ↓
  └────────┴───────────┴──────────────┴────── BLOCKED ─┘
```

## Contract Compliance

Per NSEC §18 (Contract First): all implementations of the Delivery Controller MUST obey this contract. Gating logic may be extended but never weakened.

## Integration Points

- `src/nexara_prime/evidence.py::EvidenceStore` — evidence verification
- `src/nexara_prime/governance.py::PolicyEngine` — risk assessment
- `src/nexara_prime/config.py::Settings` — environment configuration
- `scripts/governance/validate_nsec.py` — NSEC validation
- `scripts/governance/detect_nsec_drift.py` — drift detection
