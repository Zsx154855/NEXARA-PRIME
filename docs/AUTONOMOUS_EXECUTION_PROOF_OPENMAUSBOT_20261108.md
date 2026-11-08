# NEXARA x OpenMausBot — Autonomous Execution Proof (AEP-01)

**Status:** CONTRACT TESTED; LIVE AGENT EXECUTION NOT YET VERIFIED
**Date:** 2026-11-08
**Stack:** NEXARA-PRIME Cognitive Bootstrap PR #57 + OpenMausBot v0.1.148 published CLI
**Scope:** independent NEXARA-PRIME agent brain (NOT BLACK FACTORY / UNSEEN).

## Architecture

- NEXARA owns cognitive goals, top-level mission ID, knowledge, evaluation and final quality determination.
- OpenMausBot owns its Agent conversation, child-job tree, subprocess execution and team coordination.
- Adapter is thin. It does not copy OpenMausBot's scheduler or grant new permissions.
- Internal cognition and idea generation are autonomous. External commands operate within the existing, independently configured experimental execution scope.
- OpenMausBot's external Bot API is intentionally chat-only. For task execution use its published headless CLI / MCP.
- OpenMausBot state=settled is NOT success. Only state=completed and no failed children count as a reported task completion.
- Three completed Bot nodes are evidence of delegation as reported by OMB, NOT proof that independent code QA passed.

## Implemented contract

Source: src/nexara_prime/integrations/openmausbot_execution.py

1. Caller provides an existing dedicated OpenMausBot bot ID + thread ID for each NEXARA mission.
2. NEXARA stores mission ID, objective, stable target, and a deterministic send_id in local SQLite before sending.
3. CLI: openmausbot send --bot BOT - --task THREAD --send-id ID --url URL --json --quiet. Objective text goes to stdin, not argv.
4. CLI response must contain the matching taskId and a messageId. An absent acknowledgement cannot become success.
5. After acknowledgement, run: openmausbot wait --bot BOT --task THREAD --timeout 60s --strict --url URL --json --quiet.
6. Exit 3 -> NEEDS_INPUT, 4 -> RUNNING, 5 after send -> WAITING_FOR_DEVICE (offline; wait later, do not resend), 1 -> EXECUTION_FAILED, exit 0 + state=completed + no failed children -> REPORTED.
7. REPORTED = runner reports completion, NOT independent QA. The returned team evidence explicitly sets qa_verified=false.
8. Cognitive proposal handoff is implemented via ExecutionProof.submit_proposal(), accepting HYPOTHESIS or EVIDENCE_BACKED goals. This grants no production permission.
9. Recreate TaskLedger using the same SQLite database on process restart. Retried sends use the same send_id and pinned task thread, so the OMB server can deduplicate them.
10. A SQLite UNIQUE index on (bot_id, thread_id) prevents separate NEXARA missions from binding one OpenMausBot task, including across separate database connections.
11. Persisted final REPORTED or EXECUTION_FAILED receipts cannot be overwritten by stale, in-flight reconciliation results.
12. An OpenMausBot CLI transport timeout is recoverable; it is not proof of a failed job. A completed reply without a valid job tree is NOT a successful execution.

## Test evidence

Command: python -m pytest -q tests/integrations/test_openmausbot_execution.py

There are 19 isolated contract test cases. They execute a real subprocess which emulates published OpenMausBot CLI JSON and exit codes, testing restart, retry, offline, timeout, needs-input, status correctness, distinct bots in task tree, conflicts, mismatched acknowledgements, token-file isolation, free cognitive goal handoff, cross-connection thread uniqueness, stale terminal receipts, CLI timeouts before/after send, and malformed job-tree receipts.

**19 PASS, 0 FAIL** in a local Python 3.13 pytest environment using a corresponding local mirror. This is not the actual OpenMausBot binary or the complete NEXARA repository.

**Repo-native pytest, full CI, Ruff and a real OpenMausBot backend were not executed.** Never label a simulated three-bot response a successful real multi-Agent run.

## Live-proof runbook (when actual Mac is reachable)

1. Prepare a synthetic public test worktree. Check OpenMausBot CLI version and server health with the doctor command. Select only existing no-cost model access until separate approval for paid use.
2. Set up one Lead bot or room and three actual roles: Researcher, Engineer, Auditor. Provision a dedicated conversation task for the NEXARA mission; record real bot ID and thread ID.
3. Store any required pair token outside GitHub in a restricted-permission file.
4. Instantiate TaskLedger with a lab SQLite path and OMBCLI with an explicit loopback or trusted HTTPS endpoint and optional token-file.
5. Fetch a persisted NEXARA CognitiveGoal proposal and call ExecutionProof.submit_proposal(proposal, bot_id, thread_id). Resume with ExecutionProof.reconcile(mission_id); restart the calling process and test that no duplicate task is sent.
6. Capture the real OpenMausBot job tree, command process receipts, code diff, test result and human input request if any. Verify the generated artifact independently before marking learning evidence accepted.
7. Compare token cost, runtime, number of prompts/resumptions, recovery correctness and actual test success against a single-Agent baseline.

## Gates and status

| Gate | Acceptance | Current |
|---|---|---|
| A | 19 CLI-contract tests | ISOLATED PASS |
| B | Full NEXARA repo tests and lint | NOT RUN |
| C | Actual OpenMausBot CLI and server | NOT RUN |
| D | Three real Agents, verified job tree | NOT RUN |
| E | Cognitive goal -> execution -> independently verified learning | NOT RUN |
| F | iPhone queue, Mac offline/reconnection | NOT RUN |

## Constraints and remaining risks

- No permanent daemon, deployment, CI workflow modification, purchase, model call, Mac access, secrets or main merge in this PR.
- Autonomy B applies to real external side effects, not internal thoughts, hypotheses or research.
- User's new fixed cloud cost initial target is zero; upper bound THB 300/month.
- This proof expects a dedicated existing thread and does not provision it. A persistent SQLite uniqueness constraint prevents two mission IDs using the same bot/thread, but does not provide a full distributed lease or authenticated multi-host task owner.
- SQLite TaskLedger is a standalone *laboratory correlation ledger*, not a substitute for NEXARA's canonical production Mission Store. Production adapter integration must store this mapping in canonical NEXARA records and avoid competing schedulers.
- A content hash or server claim cannot replace independent test evidence and real process exit receipts.
- Review OpenMausBot GitHub Issues #4840 (Codex long-running commands) and #4832 (cross-project scoping) before live use.
- Full integration requires binding the adapter to the actual NEXARA Mission Kernel; no duplicate scheduler should be installed.

## 2026-11-08 continuation: durability hardening

- Updated isolated adapter and tests directly on stacked PR #58.
- Added cross-process SQLite uniqueness and terminal-state non-regression; improved CLI timeout recovery and malformed completion detection.
- Current local adapter mirror: **19/19 tests PASS** (Python 3.13). This does not certify real OpenMausBot, the complete NEXARA repo, the Mac, or external Agent execution.
- CI workflow requires self-hosted macOS ARM64 and is not running in this environment. No cloud runner, paid service, or permanent Agent started.
