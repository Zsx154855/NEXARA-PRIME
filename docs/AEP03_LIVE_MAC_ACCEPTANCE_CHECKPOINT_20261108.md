# AEP-03 | Real OpenMausBot multi-Agent + cognitive transfer acceptance checkpoint

Status: **LIVE_EXECUTION_BLOCKED**. This is a reviewable handoff and evidence contract, **not** proof that a Mac or real OpenMausBot ran. Frozen: 2026-11-08.

## Repository and stacked PR truth

- Product: **NEXARA-PRIME** (explicitly not BLACK FACTORY / UNSEEN).
- PR #57: `work/cognitive-bootstrap-20261108`, HEAD `96d7628d69413a244d83bbe59ef143f5ab11a4bb`, base `main`, Draft.
- PR #58: `work/openmausbot-autonomous-proof-20261108`, HEAD `f994e06a2c3897f4b7ca48ca4f71a281e06389c8`, base PR #57 branch, Draft.
- This AEP-03 branch is stacked on PR #58. No main merge.
- Current repository CI `.github/workflows/ci.yml` requests `[self-hosted, macOS, ARM64]`. No native CI result was visible for the frozen PR #58 head when this handoff was prepared.
- OpenMausBot v0.1.148 public CLI documentation: [headless-cli.md](https://github.com/milind-soni/OpenMausBot/blob/v0.1.148/docs/headless-cli.md). Installed Mac binary/version, model availability and runtime health: **NOT_VERIFIED**.

## Mac Bridge truth and scope

The owner-authorized GitHub Issue #56 has past Mac Bridge v0.2 **real** test receipts for older Draft PRs #53/#54/#55. Each older full suite reported **six failures**, and focused suites passed. The v0.3 `diagnose_gate0_logs` command is a narrowly scoped historical log-inspection operation; the latest known issue comments contain **no confirmed successful AEP-03 execution endpoint**. It is not an arbitrary shell or OpenMausBot dispatcher. Do not submit a novel operation to the old bridge and assume it will execute. Do not run the public comments as shell commands. A separate one-shot local invocation is necessary.

## Required local acceptance (one-shot; zero incremental provider fees)

1. **Gate A:** On the real Mac, read-only inspect actual Git repository, dirty changes, installed OpenMausBot CLI help/version, running service health, OpenMinis coexistence, Python/SQLite/pytest, exact PR #57 and #58 SHA ancestry. Use isolated `git worktree`; never reset or clean the user's original worktree. Test main/#57/#58 with comparable baselines and log every exit/sha. Do not dismiss six old cross-PR failures without identical-condition comparison.
2. **Gate B:** Generate a fresh synthetic Python Git lab, then run an actual OpenMausBot Lead (optional), **Researcher**, **Engineering**, **Independent QA** team. Record real bot/thread/child IDs and independently observable work by each agent. A three-node fake fixture is not enough.
3. **Gate C:** Use PR #58's official OpenMausBot CLI adapter: `run --wait none` captures `since_ms`, `wait --since` must correlate fresh results, stable `send_id` prevents duplicate sends. `REPORTED` is not `VERIFIED`. Require all children terminal, distinct real agent contributions, independent QA exit and diff evidence.
4. **Gate D:** With only disposable processes, test client exit, lost connection, adapter restart, SQLite persistence, duplicate resume, stale prior receipt, incomplete child tree. Never restart the Mac or kill unrelated agents.
5. **Gate E:** Create Task A goal through NEXARA's actual `AutonomousGoalLoop.tick` (not a handwritten synthetic proposal), use existing mission/kernel authorization for experimental patching, verify test evidence, persist via canonical `EvidenceStore`, `MemoryController` / `ExperienceLearner`, retrieve from new process and use in distinct Task B. Compare with independent Task B control baseline; metrics unavailable in actual runtime are `NOT_VERIFIED`, not zero.

**Important Cognitive Bootstrap gap:** current `AutonomousGoalLoop._approved_signals` admits only `fix_failing_tests` (read-only audit) and `audit_recent_changes` (read-only audit). A real autonomous repair mission needs a lawful existing Kernel/Mission compilation step; cannot silently convert an R0 proposal into write authority. Current `EvidenceGatedLearning.evaluate` additionally requires same `mission_id` and `suite_id`, and tokens must actually be measured; cross-mission Task A→B transfer should use `ExperienceLearner`/memory with real evidence, not fabricate comparable token metrics.

## One-shot package delivered in the ChatGPT conversation

`AEP03_LIVE_MAC_PACKAGE.zip` includes:

- `AEP03_MASTER_HANDOFF.md`: unfragmented executable engineering plan for the Mac Agent.
- `aep03_local_gate.py`: zero-dependency read-only environment/CLI probe, synthetic Git repositories for Task A and two Task B groups, native Python unittest evidence+SHA verifier. It does NOT install, start or pay for models.
- `README.md`, `SHA256SUMS.txt`: usage and integrity.

The pack was built in the ChatGPT tool container, **not on the Mac**. The one-shot generator created three *real synthetic Git projects* and native Python tests proved pre-fix failures; one synthetic task A was manually fixed and re-tested passing in a separate process; tampering with original tests was rejected. This is verification of fixture/test tools, NOT a real OpenMausBot run and NOT evidence of cognitive transfer.

## Skills evidence

Current callable `skills__list` entries did not expose the four owner-defined personal Skills:
`持续自主研发总控`, `受控执行器与故障恢复`, `智能体能力评测`, `HTML 图解回答`. Mark each `SKILL_ACCESS_BLOCKED`, not `not installed`. No callable Token optimization skill discovered; use incremental reads, pinned SHA, minimal per-agent context and resumable checkpoints. The installed `skills://plugins/data/validate-data/skill.md` **was read and applied** for evidence/metric separation; it does not impersonate personal Skills.

## Evidence admission and decision

A genuine acceptance receipt needs: frozen commit SHAs, local environment summary, actual OpenMausBot version, real bot/thread/assignment IDs, deterministic send ID, persisted `since_ms`, full task tree and each leaf's end state, actual OS subprocess exit/log SHA, reviewer identity distinct from executor, Git diff, QA audit, memory/evidence IDs, independently observed Task B retrieval/use, token and cost evidence (or honest unknown). Raw logs and secrets must stay on Mac; GitHub receives sanitized counts/hashes only.

| Gate | Current checkpoint | Why |
|---|---|---|
| A | BLOCKED | Mac not callable from current ChatGPT; no PR #57/#58 native regression |
| B | BLOCKED | No real OpenMausBot service/three-agent run |
| C | PARTIAL | Official CLI source and prior fake adapter contracts inspected; no live verified receipt |
| D | PARTIAL | SQLite/CLI recovery previously emulated; no real Mac interruption |
| E | BLOCKED | No actual Task A evidence, cross-session retrieval or Task B transfer |

No merge, production updates, paid model calls, permanent service, arbitrary Mac execution or unapproved secrets occurred in preparing this checkpoint.

### Definitive next execution

Once a real Mac operator/Agent can access the package and an authorized zero-incremental-cost OpenMausBot instance, run the pack's `probe` first, then follow `AEP03_MASTER_HANDOFF.md` without a new brainstorming stage. Do not claim acceptance until the evidence above exists.