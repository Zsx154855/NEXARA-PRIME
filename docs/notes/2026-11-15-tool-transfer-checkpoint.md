# Checkpoint — real tool-level A→B transfer (2026-11-15)

- Status: DELIVERED (engineering slice); MOCK_INTEGRATION only.
- Branch: `work/cognitive-autonomy-01-20261115`; commits `926d484`, `174c742`.
- PR: #76 (Draft, not merged; base unchanged).

## What changed
- `ToolRuntime.invoke` now persists nonzero process exits as `status=failed` and
  raises; replay of a failed invocation raises `tool_replay_failed`.
- `src/nexara_prime/tool_transfer_experiment.py`: Task A records experiences from
  real `code_exec` / `run_command_sandboxed` receipts across two missions; Task B
  cold, experienced, and revoked arms each re-execute a real tool.
- Tests: `tests/test_tool_exit_status.py`, `tests/test_tool_transfer_experiment.py`.

## Evidence (run 2026-11-15, worktree at 174c742)
- `pytest` full suite: **2444 passed, 3 subtests passed in 64.86s** (committed tree).
- Focused suite: 4 passed; experiment result: cold=False, experienced=True,
  revoked=False; real tool outcome delta=+1; decision action=`code_exec`,
  based_on=2, based_on_missions=2, verified evidence ids present.
- Independent QA (read-only, commit 926d484): **PASS-WITH-NITS**. Nits D1/D3/D4
  fixed in 174c742; D2 partially closed (returncode/stderr now surfaced; failure
  code remains `RUNTIME_INTERNAL`). QA scope: 926d484, not 174c742.

## Boundary
- Harness-defined tool pair with deterministic commands; n=1 trial per arm.
  This is wiring evidence for receipt-bound tool selection, not statistical
  cross-task generalization and not production learning proof.
- No model/provider call, no main merge, no production deployment.

## Next
- Independent re-check of 174c742 delta; then next authorized autonomous task.
