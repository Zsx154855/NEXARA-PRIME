# NEXARA-PRIME — M1 real-integration checkpoint (2026-11-12)

## Identity and authorization

Independent NEXARA intelligent-agent brain only. Prior baseline main:
`f4a5400d73391280fa9c19e128edcea03cf608f1`.
PR #68 was Draft (M0 head `2e001290332e0c6c830e051767de2d7444668c7c`).
This checkpoint advances that **same** isolated PR branch, without touching
PR #66 CAB-01, PR #67 memory contract, or main.

Authorized operations: isolated source changes, tests, Draft PR update.
Not authorized: main merge, production data, Mac Runner, paid API calls,
persistent service deployment or bypass of trusted execution boundaries.

## Implementation

- Added `src/nexara_prime/brain/mcre_mission_shadow.py`.
  `MissionShadowObserver.observe(mission, snapshot)` extracts mission identity,
  `MissionSpec.objective`, `MissionSpec.risk_level`, and existing
  `resource_budget` / `budget_usage` dictionaries (where present),
  then delegates to the existing `MCREShadow` advice engine. It does not
  mutate Mission, dispatch workers, publish events, activate skills, or
  decide on permissions. Scope/project/repo/environment are supplied by a
  separate trusted host snapshot, not inferred from user-supplied text.
- The remaining-token logic fails conservatively if budget IDs disagree,
  usage is not reported, values are malformed, or the host and Mission
  snapshots disagree. A known exhausted budget cannot be overwritten by an
  optimistic external report.
- Added `tests/brain/test_mcre_mission_shadow.py`: read-only decision
  semantics, R2 escalation, incomplete evidence, mission identity checks,
  immutable task identity, budget mismatch/exhaustion, cross-scope evidence
  reuse, unreported cost, no evidence side effects.
- Added `tests/integrations/test_mcre_real_sqlite_evidence.py`, using the
  **repository's actual** `SQLiteStore`, `EventBus`, `EvidenceStore`,
  `Mission` and `MissionSpec`. Tests are drafted for genuine write/verify/read
  in a temporary SQLite DB, stale HEAD/scope rejection, deliberate corruption,
  and paired skill-evaluation receipts. **These integration tests HAVE NOT RUN
  successfully** (see blocker); don't report them as accepted.

## Executed and independently repeatable local scope

Interpreter: Python 3.13.5; pytest 9.0.2; no extra model/API calls.

```sh
cd /mnt/data/nexara-mcre-shadow
PYTHONPATH=src python -m pytest -q tests/brain --tb=short
# 53 passed in 0.23s (isolated module tests using synthetic Mission/EvidenceReader)
python -m compileall -q src tests
# exit code 0
```

M1 genuine repository integration attempt:
```sh
PYTHONPATH=src python -m pytest -q tests/integrations/test_mcre_real_sqlite_evidence.py --tb=short
# exit code 2 at collection: ModuleNotFoundError: No module named 'nexara_prime.db'
```
The isolated checkout contains only M0/M1 overlay modules. It does not
contain the complete NEXARA checkout, especially db.py/evidence.py/models.py.
`git ls-remote https://github.com/Zsx154855/NEXARA-PRIME.git HEAD`
exited 128: `Could not resolve host: github.com`.
This is ENVIRONMENT_BLOCKED, **NOT a product regression**, and **not a PASS**.
The attempt log has SHA256:
`f043debc080f11cfaabdf895efdcfc752ffc987afc4a37d297e95f81c56fb9b6`.

## Acceptance remaining — REQUIRED

1. Restore full repo with exact PR #68 head in a verified isolated
   Python 3.12+ environment with sufficient disk and no production secrets.
2. Run `python -m pytest -q tests/brain/test_mcre_shadow.py
   tests/brain/test_mcre_evidence_binding.py
   tests/brain/test_verified_skill_evolution.py
   tests/brain/test_mcre_mission_shadow.py
   tests/integrations/test_mcre_real_sqlite_evidence.py`
   and then full repo regression. Capture exit status, test counts, log
   SHA256, environment and HEAD. Do NOT use CI on the unverified self-hosted
   Mac Runner or charge paid services.
3. Real EvidenceStore end-to-end must independently confirm
   `is_preverified_and_integrity_bound()` + `verify_artifact()`,
   original record/verification transitions, stale/cross-scope protection,
   tamper detection, and reviewer/issuer authenticity (currently NOT_PROVEN).
4. Observe a real Mission through an opt-in, read-only Runtime adapter and
   compare shadow advice with actual authorized outcomes. **This PR does
   not hook into the running Mission lifecycle yet.**
5. Unseen experiment: real Task A to Task B transfer with sealed holdout and
   independent QA. Historical treatment=46 turns vs control=35 is negative
   efficiency evidence. No real improvement demonstrated.
6. Do not formalize or activate skills before CAB-01 approval chain,
   PR #67 memory compatibility and independent quality results are resolved.

## Evidence statuses

- VERIFIED: GitHub baseline/PR #68 branch read; isolated Python modules
  `53 passed`; local compileall exit 0; exact file Git blobs once
  compared against published commit.
- PARTIAL: typed Mission observer, read-only EvidenceStore binding,
  zero-new-cost review protocol.
- BLOCKED: real SQLite/EvidenceStore test execution (missing complete repo),
  Mac Relay/E2E, full-suite regression, CI runner.
- NOT_VERIFIED: authentic issuer / independent QA identity; model Token/cost
  measurements; OpenTelemetry real spans; true skill evolution and runtime
  opt-in adoption.
- NEVER CLAIM: production acceptance, 100% PASS, automatic learning,
  verified skills activated, ability to bypass Trusted Gate.

## Skill access

The available installed skill catalog was searched for named custom
engineering/controlled executor/agent-evaluation/Token management skills;
none matched those names. SKILL_ACCESS_BLOCKED for exact custom skills.
Equivalent no-new-cost direct engineering checks applied; this is not
evidence of activating missing skills. FastContext, Agent Lightning, DSPy
and OTel remain research references rather than installed integrations.

## GitHub CI safety

The existing repository workflows target self-hosted macOS ARM64 on PRs to
main and work/* pushes. This branch uses `[skip ci]` commit messages while
the resource gate is unverified. CI_NOT_RUN != CI_PASS; no manual reruns
without explicit runner resource check and authorization.
