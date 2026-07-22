# NEXARA Delivery Controller Contract V2

**Contract ID**: `DELIVERY_CONTROLLER_CONTRACT_V2`
**Version**: 2.0.0
**Supersedes**: DELIVERY_CONTROLLER_CONTRACT_V1
**Governed By**: NSEC V2.0 §18, §28, §43-§45
**Status**: ACTIVE
**Effective**: 2026-07-22

---

## Purpose

The Delivery Controller ensures that no Feature, Mission, or PR enters GitHub without first passing automated readiness gates. V2 adds external reality detection and unified evidence schema enforcement.

## V2 Additions

### G9_EXTERNAL_REALITY

Detects external blockers beyond local file system inspection:

| Check | Method | Source |
|-------|--------|--------|
| GitHub Actions billing lock | Read AGENTS.md for "billing lock" keyword | AGENTS.md |
| CI never executed | Read RECEIPT.json `ci_status` field | reports/*/RECEIPT.json |
| External CI execution capability | Check `.github/workflows/` for `runs-on` directives | .github/workflows/ |
| Known external blockers | Aggregate all documented external blockers | AGENTS.md + RECEIPT.json |

G9 PASSES when: no external blockers documented OR all external blockers are acknowledged with local-verification-authoritative policy.
G9 FAILS when: external blockers exist AND no local-authoritative override is documented.
G9 WARNS when: external blockers exist but AGENTS.md declares local verification as authoritative.

### Evidence Schema Contract (unified)

All evidence files MUST conform to at least one of:

**Minimal Schema** (any evidence):
```json
{
  "evidence_id": "<string>",
  "sha256": "<64-char hex>",
  "timestamp": "<ISO 8601>"
}
```

**Full Schema** (runtime evidence):
```json
{
  "evidence_id": "<string>",
  "sha256": "<64-char hex>",
  "timestamp": "<ISO 8601>",
  "mission_id": "<string>",
  "kind": "<string>",
  "content": "<string>",
  "source": "<string>"
}
```

**Legacy Detection**: Files missing `evidence_id` or `sha256` are flagged as LEGACY_SCHEMA.
They are NOT blocking but generate a warning for migration.

## Delivery Gate States (V2)

| State | Meaning |
|-------|---------|
| `INIT` | Controller initialized |
| `AUDITING` | Running environment and repo scans |
| `VERIFYING` | Running test suite and static checks |
| `EVIDENCE_FREEZE` | All evidence collected and hashed |
| `READY_FOR_COMMIT` | All local gates passed; external blockers noted |
| `READY_FOR_PR` | All gates passed; external blockers acknowledged |
| `BLOCKED` | Local gates failed |
| `EXTERNAL_BLOCKED` | G9 detected unacknowledged external blocker |

## Gate Definitions (V2)

| Gate | Name | V2 Change |
|------|------|-----------|
| G1 | Environment | unchanged |
| G2 | Repository | unchanged |
| G3 | Contract | unchanged |
| G4 | Test | unchanged |
| G5 | Evidence | upgraded: schema contract enforcement + legacy detection |
| G6 | Receipt | unchanged |
| G7 | CI Dependency | unchanged |
| G8 | Review Readiness | unchanged |
| G9 | External Reality | NEW: detects billing lock, unprovisioned CI, external blockers |

## Evidence Schema Contract (formal)

```python
EVIDENCE_MINIMAL_REQUIRED = {"evidence_id", "sha256", "timestamp"}
EVIDENCE_FULL_REQUIRED = {"evidence_id", "sha256", "timestamp", "mission_id", "kind"}
EVIDENCE_LEGACY_INDICATORS = ["mission", "branch", "base_sha", "head_sha"]  # old schema fields
```

Validation rules:
1. Must be valid JSON
2. Must have at least `evidence_id` or `sha256`
3. Legacy fields without required fields → `LEGACY_MIGRATION_NEEDED` (warning, non-blocking)
4. Has required fields → `CONFORMING`
5. Has required + optional fields → `FULLY_CONFORMING`

## State Transitions (V2)

```
INIT → AUDITING → VERIFYING → EVIDENCE_FREEZE → READY_FOR_COMMIT → READY_FOR_PR
  ↓        ↓           ↓              ↓                ↓
  └────────┴───────────┴──────────────┴────── BLOCKED ─┘
                                                   ↓
                                          EXTERNAL_BLOCKED (G9)
```
