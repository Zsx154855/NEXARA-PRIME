# Checkpoint — real tool-level A→B transfer (2026-11-15)

- Status: DELIVERED (engineering slice); MOCK_INTEGRATION only.
- Branch: `work/cognitive-autonomy-01-20261115`; commits `926d484`, `174c742`, `d7de535`, `fa57c0e`.
- PR: #76 (Draft, not merged; base unchanged).

## What changed
- `ToolRuntime.invoke` now persists nonzero process exits as `status=failed` and
  raises; replay of a failed invocation raises `tool_replay_failed`.
- `src/nexara_prime/tool_transfer_experiment.py`: Task A records experiences from
  real `code_exec` / `run_command_sandboxed` receipts across two missions; Task B
  cold, experienced, and revoked arms each re-execute a real tool.
- Tests: `tests/test_tool_exit_status.py`, `tests/test_tool_transfer_experiment.py`.

## Evidence (run 2026-11-15, worktree at 922007e)
- `pytest` full suite: **2444 passed, 3 subtests passed in 68.77s** at `d7de535`
  (before the 3-trial test-only change).
- Focused suite: 4 passed; 3 trials per arm: cold=0.0, experienced=1.0,
  revoked=0.0; real tool outcome delta=+1.0; decision action=`code_exec`,
  based_on=2, based_on_missions=2, verified evidence ids present.
- Independent QA (read-only): **PASS-WITH-NITS** at `926d484`; **PASS** on the
  `174c742` delta. Nits D1/D3/D4 fixed; D2 closed at `d7de535` with
  `FailureCode.TOOL_EXECUTION_FAILED` / `ReasonCode.EXECUTION_FAILED`.

## Boundary
- Harness-defined tool pair with deterministic commands; n=3 trials per arm
  (all identical by construction). This is wiring evidence for receipt-bound
  tool selection, not statistical cross-task generalization and not production
  learning proof.
- No model/provider call, no main merge, no production deployment.

## Next
- Final independent QA passed at 922007e (including D2/trials); next authorized
  autonomous task TBD. The 0/1/0 rates are deterministic by construction and
  must not be cited as statistical variance.


## Scoped-revocation repair — subsequent code checkpoint (2026-11-15)

- Following static review, `tool_transfer_experiment.py` no longer archives all active `experience` rows. It scopes revocation to the two newly created Task A mission IDs via existing `ExperienceLearner.retire_experiences(mission_id=...)`.
- `retirement_audit` now retains mission ID, reason, actor, count and timestamp for the revoked Task A records.
- The existing A→B regression now asserts two retirement audit events with two rows each. A new regression seeds an unrelated active experience in the same isolated SQLite store, executes the experiment, and checks that unrelated memory stays active while Task A rows are archived.
- Code commits: `83f20ba` and `3a4cbba`. **No test run or independent QA has yet been verified for these new commits**; earlier 2444-passed results are historical evidence at `922007e`, not proof for the new head.
- QA to run on pinned current HEAD: `python -m pytest tests/test_tool_transfer_experiment.py tests/test_tool_exit_status.py -q -ra`, then the full authorized suite. Preserve raw test exits and environment; avoid production DB and paid providers.
- Remaining limits: `MOCK_INTEGRATION`; deterministic identical repeated commands (n=3 per arm), no claim of statistical generalization; ADR-008 production Runtime wiring and real DSH/P3/CAB Mission authorization remain out of scope.
