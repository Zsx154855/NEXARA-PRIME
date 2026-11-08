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

## Operational and security boundaries

- CognitiveStateStore reconstructs immutable project-scoped revisions, checks parent integrity anchors, and rejects stale writes. Only a trusted owner authorization callback can allow core identity, owner goals, beliefs or commitments changes. An Agent can update only hypotheses/uncertainties with verified evidence.
- AutonomousGoalLoop.tick converts verified, event-bound observations into R0, cost-zero proposals ONLY when an injected trusted event authorizer accepts every signal. Without an event authorizer it fails closed and emits no proposal. Every proposal has execution_authorized=false; retry does not duplicate. It NEVER calls tools.
- EvidenceGatedLearning.evaluate parses metrics from two mission-bound, verified evidence records. An injected trusted auditor authorization callback and distinct executor/auditor are required. Only zero-failure, non-empty tests on the same explicit suite_id with non-regressing pass count and strictly reduced measured tokens produce REVIEWABLE; otherwise REJECTED. Both results remain inactive.
- The owner and auditor callbacks MUST be wired to the existing server-side identity/approval authority before production. Never use unconditional allow lambdas except tests.
- A hash-verified EvidenceArtifact is not proof its claims about the external world are true. Runner attestation and exact log references are a separate gate.
- A source_event_id binding does not authenticate an external event producer. The event_authorizer callback must be backed by a trusted producer identity and checked per project; a permissive lambda is for isolated tests ONLY.
- This patch is opt-in. It does NOT create daemon, schedule, Mac remote control, paid model calls, human approval, or policy activation.

## Actual tests and limits

- Compatibility harness used local Python 3.13 + pytest 9, a SQLite-compatible test store and evidence doubles: **12 PASS**; syntax compilation: PASS.
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
