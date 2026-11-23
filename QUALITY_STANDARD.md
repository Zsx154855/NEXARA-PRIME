# Engineering Definition of Done

Every change on a branch must pass **all** of these before it is offered as a PR.
The bar is mechanical: if a gate cannot be run, the change is not done.

## 1. Scope
- One task per branch; the PR states the task id and what is *not* in scope.
- No drive-by refactors in a behaviour change. Separate commits.

## 2. Tests
- New behaviour: a failing test first, then the implementation (evidence in the PR).
- Bug fix: a regression test that fails on the parent commit.
- No test is deleted or weakened to make a gate green. If a test encoded a lie
  (e.g. asserting a fake sandbox), the change to the test is explained.

## 3. Gates (run by `scripts/quality/gate.sh`)
| Gate | Command | Pass condition |
|---|---|---|
| import/compile | `python -m compileall -q src` | exit 0 |
| lint | `ruff check <changed py files>` | exit 0 |
| unit/integration | `bash scripts/test_linux.sh` | exit 0 |
| UI↔API truth | `python scripts/ui/route_truth.py` | `missing == []` |
| gate status | `python scripts/governance/derive_gate_status.py` | parses; no PASS without evidence |
| secrets | `python scripts/security/scan_hardcoded_secrets.py` | exit 0 |

## 4. Security
- No secret in code, tests, logs or reports.
- New network calls are deny-by-default and opt-in.
- A security-relevant change (auth, sandbox, execution) needs an independent
  review: a second agent reads the diff and the tests, not the author's summary.

## 5. Documentation
- `CHANGELOG.md` entry under `## [Unreleased]`.
- An ADR in `docs/adr/` for every irreversible or security-relevant decision.
- README updated when user-visible behaviour changes.

## 6. Rollback
- Every PR states how to revert (commit revert vs data migration).
- Schema/data changes ship with a forward fix or a documented manual step.

## 7. Evidence
- The PR body lists each gate as `command → exit code → one-line result`.
- Claims without a command are marked `UNVERIFIED`.

## 8. Review
- Author never approves their own security or architecture change.
- Review comments are resolved or explicitly deferred with a reason.
