# NEXARA-PRIME MCRE Shadow + Verified Skill Evolution — M0 isolated checkpoint

Date: 2026-11-12. Baseline: main `f4a5400d73391280fa9c19e128edcea03cf608f1`.
Scope: independent cognitive agent brain; NOT the NEXARA film factory.
Status: ISOLATED_SOURCE + ISOLATED_TESTS; NO RUNTIME ADOPTION / NO PROD ACCEPTANCE.

## Existing system preserved

Do not replace `brain.meta_cognition.MetaCognitionController`, `brain.reasoning_budget.ReasoningBudgetManager`,
`resource_budget.ResourceBudgetManager`, `cost_governor.TokenGovernor`, `brain.evolution_engine.EvolutionController`,
`brain.memory_controller.MemoryController`, `runtime.NexaraRuntime`, Scheduler/Workers, ApprovalEngine,
Trusted Gate, or existing EvidenceStore. This branch adds three passive helpers only; no imports
into active Runtime, no model calls, databases, network, timers, workers or external side effects.

## Implementation and interfaces

* `brain/mcre_shadow.py` — Deterministic `MCREShadow.advise()` returns RESEARCH/REUSE/ESCALATE/DEFER
  as an advisory recommendation, never an execution authorization. Cache reuse requires
  project ID, exact repo revision, environment ID, scope ID and digest to match, PLUS a trusted
  callback that validates the ENTIRE `ContextRef` against the EvidenceStore receipt.
  Merely providing an existing evidence_id is insufficient. No evidence resolver means no reuse.
  Task key is a project+objective+HEAD+environment+scope fingerprint, for suggestion/dedup
  assessment ONLY: do not treat it as an idempotency key for external writes.
  Unknown measured costs remain None, not $0. OTel-like `nexara.mcre.*` are local
  experimental attributes, not standardized GenAI semantic-convention metrics.

* `brain/verified_skill_evolution.py` — `VerifiedSkillEvolution.assess()` evaluates
  candidate vs control on at least three paired, unseen, independently reviewed tasks;
  requires a source-backed rollback ref, separate candidate author/reviewer, exact
  trial-evidence verification against external authoritative records, no regressions
  in pass/fail, turns, or reported token consumption. It only returns
  `ELIGIBLE_FOR_REVIEW`, never activates a Skill or overwrites production policy.
  The external verifier MUST bind the entire `Trial` (not just evidence ID).
  Three pairs are a *minimum safety smoke requirement*, not statistical proof of transfer.
  Holdout data must be independently chosen and sealed before optimization.

## Executed isolated tests

Command: `python -m pytest -q --tb=short` from an isolated directory containing
the three new standard-library-only modules and their tests.
Observed after the incremental binding repair: `38 passed in 0.13s`, Python 3.13.5, pytest 9.0.2; no paid model calls.
See `tests/brain/test_mcre_shadow.py`, `tests/brain/test_verified_skill_evolution.py`, and `tests/brain/test_mcre_evidence_binding.py`.
Git object SHA readback must match the local files before this result can be
associated with the committed branch. This is NOT a full-repo test.

## Mandatory next gates (not passed here)

1. Run pinned entire checkout with Python >=3.12 and check targeted+full regressions.
2. Audit and build a real EvidenceStore adapter that verifies immutable byte digests,
   revision, environment, authorization scope, test outcomes and independent reviewer.
3. Bind advisor in Shadow Mode to existing Mission/Controller/TokenCompiler; no automatic
   execution, scheduling or billing decisions until independent QA.
4. Emit proper OpenTelemetry GenAI spans via existing telemetry without recording raw
   credentials, prompts or source content; retain None/UNKNOWN for unavailable provider cost.
5. Reuse FastContext-style read/glob/grep evidence selection and Agent Lightning Skill/DSPy
   eval methods only after compatibility audit; do not install new models, GPU or paid APIs.
6. Resolve PR #66 Runtime issuer/ingress and PR #67 memory kind/evidence lineage separately.
   Do not touch either Draft PR here or mistake this work for CAB closure.
7. Run real Task A->B unseen transfer with counterfactual controls and stable resource
   baselines. Historical treatment 46 turns vs control 35 turns, equivalent passing
   tests, is NEGATIVE evidence for efficiency gain—not a Verified Skill Evolution.
8. Existing AutonomousBoundary and operator approvals remain authoritative for any
   activation and rollback. No main merge, persistent service or production deployment.

## Evidence labels

VERIFIED: GitHub main/PR existence and source structure read through connected GitHub;
          38 isolated pytest tests on the candidate file bytes.
NOT_VERIFIED: full repository import, real GitHub CI, Mac Relay execution, integration
              with durable job recovery, live safety checks, real cost savings, genuine
              independent transfer and skill promotion.

## Incremental evidence-binding improvement

Added `mcre_evidence_binding.EvidenceStoreBinding`, a read-only adapter to the
existing `EvidenceStore.is_preverified_and_integrity_bound` and
`EvidenceStore.verify_artifact` public methods. Context manifests use kind
`mcre_context` and bind project, HEAD, environment, scope and SHA-256 of
stored content. Trial receipts use kind `skill_eval_trial`, binding reviewer,
variant, pass/fail, step count, tokens and observed cost. These are proposed
future receipt *types*, not claimed existing production writers.

Trust caveat: integrity of a stored receipt is not independent validation of
its issuer, independent QA role or external repository HEAD. Until a trusted
issuer and version resolver are wired through the existing CAB and EvidenceStore,
these methods can support only shadow recommendations, never authorization.

Skill comparison now refuses cost regression and treats missing cost measurements
as `COST_METRICS_UNKNOWN`; no cost may be inferred from an absent field.
The positive test fixture is synthetic, not proof of actual skill improvement.


## CI resource gate and review authorization

Repository default `.github/workflows/ci.yml` triggers on `work/*` pushes
and PRs to `main`, using a self-hosted macOS ARM64 runner. Historical Mac
disk/runtime prerequisites remain NOT_VERIFIED in this turn. Accordingly this
checkpoint commit explicitly carries `[skip ci]` to prevent accidental
automatic resource-consuming Mac checks when opening the Draft PR.
This is CI_NOT_RUN, **never CI_PASS**; skip directives may leave required checks
pending and must be lifted only after authorized runner resource inspection.
Do not rerun existing blocked CI or dispatch workflows to bypass this gate.

Engineering quality remains isolated-test PASS / integrated regression NOT_RUN.
No merge authorization is implied. The independent review should first compare
blobs and pin current parent base, then run real SQLite and full repository
tests in a verified isolated runner. Keep the rollout as a read-only Shadow Mode
proposal until separate QA and human authorization.
