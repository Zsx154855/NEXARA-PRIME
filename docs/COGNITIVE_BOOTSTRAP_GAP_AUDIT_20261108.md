# Cognitive Bootstrap — Gap Audit and Isolated Phase 1

Baseline: main @ f4a5400d73391280fa9c19e128edcea03cf608f1 (2026-11-08).
Scope: standalone NEXARA-PRIME agent-brain project, NOT BLACK FACTORY / UNSEEN.
Status: **ISOLATED IMPLEMENTATION / NOT PRODUCTION ENABLED**.

## Evidence-based gaps

| Capability | Existing implementation | Gap and current resolution |
|---|---|---|
| Cognitive State | brain/cognitive_models.py, world_model.py, meta_cognition.py, memory_controller.py | Independent components with in-process state; contradiction counter currently returns zero. Added opt-in immutable version chain. |
| Autonomous Goal Loop | brain/goal_manager.py, scheduler/autonomous_scheduler.py, environment/intelligence.py | Goals and schedules primarily in memory; no durable governed event-to-admission bridge. Added idempotent, verified-evidence-backed, R0 advisory proposals only. |
| Evidence-Gated Learning | brain/experience_learner.py, evolution_engine.py, evidence.py, evolution/boundary.py | Evolution proposals can become internally approved from scores; no uniform independent-evaluation binding. Added non-activating REVIEWABLE / REJECTED candidates. |

These are static default-branch findings, NOT proof that other branches or currently installed Mac components lack the capability.

## Reused engineering contracts

- Canonical nexara_prime.db.SQLiteStore: save_record_if_absent, get_record_envelope, list_record_envelopes. No new database manager/migration.
- nexara_prime.evidence.EvidenceStore: is_preverified_and_integrity_bound, get_by_id. Evidence must already be verified and bound.
- SignalAnalyzer from brain/environment/intelligence.py: two allowlisted read-only audit objectives, not general autonomous command execution.
- ChiefBrainKernel / PolicyEngine / ApprovalEngine / runtime continue to own mission admission, execution and human approvals. No direct runtime dispatch in this patch.

## Cognitive freedom by default; external effects remain governed

This revision separates **thought** from **action**. The cognitive kernel must not be forced to seek approval before brainstorming, questioning, updating its own tentative hypotheses, proposing goals or testing learning ideas.

- CognitiveStateStore permits Agent hypotheses and uncertainties to persist with no EvidenceStore artifact. Such revisions are explicitly marked TENTATIVE and cannot directly overwrite owner-defined identity, goals, commitments or established beliefs. Changes to owner-controlled fields still require genuine owner authorization and an evidence artifact.
- AutonomousGoalLoop.tick can propose read-only investigations from unverified signals with no authorizer or evidence. These are explicitly HYPOTHESIS, never runtime permission. Trusted and evidence-linked observations can produce EVIDENCE_BACKED proposals. Both are idempotent and execution_authorized=false; existing Kernel handles real-world action.
- EvidenceGatedLearning.evaluate allows the Agent to self-review results without a separate authenticated auditor, yielding PROVISIONAL suggestions. Same-suite tests with improved quality and lower tokens can become REVIEWABLE when a genuine independent auditor is authenticated. No learning candidate silently changes live policies or tools.
- Agent creativity, critique, planning, internal memory and local analysis are not blocked by enterprise-style approval bureaucracy. Identity permissions, paid actions, production writes, external publication, destructive operations and secret export are checked only at their actual execution boundaries.
- A hash-verified EvidenceArtifact does not prove that claimed real-world test results are true. Runner provenance and exact logs are required for external activation, not for thinking.
- This patch is opt-in and contains no daemon, external connector, Mac remote access, paid calls, production write, or policy activation.

## Actual tests and limits

- The earlier isolated compatibility harness reported 12 PASS before this relaxation. This revision has **15 repository-native test functions, NOT YET EXECUTED**. Do not transfer the earlier result to this head.
- Repository-native tests under tests/brain/test_cognitive_continuity.py target the real SQLiteStore/EvidenceStore.
- Actual full repository, real native EvidenceStore tests, Ruff and live Mac Bridge: **NOT RUN** in this session. These must run in the actual repository before anything is called production verified.
- Mock or test-double success never counts as a real autonomous Agent execution.

## Next acceptance gates

C0 — Repo-native pytest: python3 -m pytest -q tests/brain/test_cognitive_continuity.py, then full regression/ruff/governance. Fix any actual API mismatch.

C1 — Real SQLite/Evidence restart, tamper, concurrency, project isolation and evidence-bound proposal verification.

C2 — Connect an authenticated event source and safe Kernel admission adapter. Verify reject R2+ unless separately approved, offline wait/replay, exactly-one proposal, no tool execution until admission.

C3 — Genuine independent baseline/candidate test receipts, runner provenance, tokenizer/cost measurements, review and rollback. Never self-promote a policy or Skill.

C4 — Selectively sync approved, evidence-bound knowledge to Obsidian; keep private Vault and credentials outside public GitHub.

C5 — Verified iPhone → durable queue → awake Mac Agent → independent evidence → memory candidate → review. No paid services without separate authorization.

## Safety

Autonomy B, GitHub branch isolated; no production config, no public private data, no main merge, no deployments, no daemon and no new charges. Future cloud fixed budget cap remains THB 300/month. Existing permission gates and human veto retain full authority.
