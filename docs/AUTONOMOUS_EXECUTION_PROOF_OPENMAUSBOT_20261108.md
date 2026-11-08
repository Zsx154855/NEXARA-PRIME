# NEXARA x OpenMausBot — Autonomous Execution Proof (AEP-01)

**Status:** AEP-02 CONTRACT TESTED; LIVE AGENT EXECUTION NOT YET VERIFIED
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
3. CLI: openmausbot run --bot BOT - --task THREAD --send-id ID --wait none --url URL --json --quiet. Objective text goes to stdin, not argv. This returns a server-clock `since` anchor captured before the send.
4. CLI response must contain matching threadId, sendId, messageId, and a valid `since <= at` server-clock relationship. Queued/steered sends are not accepted as exclusive execution proof.
5. After acknowledgement, run: openmausbot wait --bot BOT --task THREAD --since SINCE_MS --timeout 60s --strict --url URL --json --quiet.
6. Exit 3 -> NEEDS_INPUT, 4 -> RUNNING, 5 after send -> WAITING_FOR_DEVICE (offline; wait later, do not resend), 1 -> EXECUTION_FAILED; exit 0 + state=completed + matching thread/epoch + every node completed + zero failed/cancelled counts -> REPORTED.
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
| A | 36 CLI-contract tests (19 original + 17 additional) | ISOLATED PASS |
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

## 2026-11-08 AEP-02: anchored job receipts and failure-mode coverage

- Source change is stacked on PR #58 only; PR #57 remains the cognitive prerequisite, and main is unchanged.
- The adapter now uses official `run --wait none` rather than `send`, because `run` returns a server-origin `since` epoch. That epoch is persisted in the laboratory SQLite correlation ledger, and all subsequent `wait` calls pass `--since`.
- An unanchored historical AEP-01 mission is migrated without inventing a timestamp, and returns `NEEDS_INPUT` rather than accepting an old job as completed. A retry whose duplicate acknowledgement predates its new anchor is also treated as ambiguous, not success.
- A `queued` or `steered` acknowledgement is not accepted as proof of a dedicated new job; use a fresh idle task/thread for the live pilot.
- Final receipts must bind the expected task/thread, contain an execution epoch not older than the submitted anchor, have a nonempty task tree with every node terminal-completed, and have no failed/cancelled counts.
- Explicit URL parsing rejects username/password authority confusion, query/fragment/path injection and non-loopback plaintext HTTP.
- **36 PASS / 0 FAIL**, Python 3.13, isolated fake CLI subprocess tests in the current sandbox. This is a local mirror, **not repository-native CI and not an actual OpenMausBot process**.
- A GitHub-only branch cannot prove Mac availability, Agent execution, independent QA, or learning quality. These remain Gate B-F.

### Exact next live test when a Mac runner is genuinely available

1. Pin the PR #58 commit, confirm a separate disposable worktree and a dedicated idle OpenMausBot bot/thread, and run `openmausbot doctor --json --url http://127.0.0.1:8799`. Do not infer readiness from the presence of a binary.
2. Run `python -m pytest -q tests/integrations/test_openmausbot_execution.py` in the full repository environment, and record the exact commit, Python version, exit code and test log hash. Run the existing repository regression separately.
3. On an isolated synthetic repository and with an explicitly available no-cost engine, provision real Researcher, Engineer and Auditor Bots. Record the actual IDs. Do not use a fabricated task tree as evidence.
4. Submit the synthetic cognitive proposal with `PYTHONPATH=src python scripts/proofs/openmausbot_execution_proof.py submit --db LAB/missions.db --proposal-json examples/aep01_cognitive_proposal.json --bot-id BOT_ID --thread-id DEDICATED_THREAD_ID`. Record its `since_ms` from the SQLite ledger.
5. Use the script's `resume --mission-id coggoal_synthetic_aep01` until a terminal status; kill/restart only the adapter process during the test, not an unrelated production service. Confirm no duplicate send and the same task ID/epoch.
6. Export the real job and independently run the actual test/diff review. `REPORTED` is only runtime completion; independent QA requires a separate verified test receipt.
7. Measure baseline versus multi-Agent outcome: actual tests passed, cost/tokens, recoverability, duplicate sends and accepted evidence. Never upgrade learned strategies solely from a model-written success statement.

No new paid services, production deployment, secrets, main merge, or Mac-local write are authorized by this document.
