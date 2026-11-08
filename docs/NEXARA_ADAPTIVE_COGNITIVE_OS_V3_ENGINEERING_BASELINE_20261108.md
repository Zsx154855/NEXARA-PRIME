# NEXARA-PRIME — Adaptive Cognitive OS V3.0 | Product / Engineering Baseline

**Authority:** Owner's explicit V3.0 direction, dated 2026-11-08. This file records an implementable distillation of that direction, **not a new competing engineering constitution**. Existing `governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md` remains the canonical engineering governance source. Verified runtime facts override unverified documentation. Scope: **independent NEXARA-PRIME, not BLACK FACTORY / UNSEEN**.

## Product north star

Continuously revise understanding of the world and own limitations; autonomously propose goals within authorized resources; execute through replaceable workers; verify real outcomes independently; transfer evidence-bound experience to unseen tasks; and measure actual capability growth, not Agent count or language fluency.

**Four logical domains**, not four new servers:

| Domain | Owns | Prefer existing |
|---|---|---|
| Cognitive | World/Self model, goals, hypotheses, reasoning, context selection, memory, metacognition | ChiefBrainKernel; CognitiveStateStore; AutonomousGoalLoop; MemoryController |
| Execution | Tools, Agent delegation, child task lifecycle, process observation | OpenMausBot via thin CLI/MCP adapter |
| Trust | Actual permissions/budget/sandbox, identity, correlation, independent evidence, recoverability | Existing PolicyEngine, KernelExecutionGuard, WorkContract, EvidenceStore, WriterLease, Mac Bridge |
| Development | Eval benchmark, strategic lessons, skill candidates, regressions and rollback | Existing ExperienceLearner / EvidenceGatedLearning; build only missing interfaces |

**Ownership:** MASTER sets goals and actual permissions. NEXARA owns cognitive intent, top-level mission identity and final acceptance. OpenMausBot owns its own execution subtree. No competing schedule/mission database or new policy authority.

## Minimum typed chain (reuse rather than rebuild)

`Cognitive Goal Proposal → MissionSpec / WorkContract → Kernel admission → OpenMausBot execution → independent evidence → accepted outcome → ExperienceLearner / memory recall → new task evaluation`.

- Proposal (existing `AutonomousGoalLoop.tick`) can remain `HYPOTHESIS` with `execution_authorized=False` while an agent reasons freely. It **never itself authorizes an external tool call**.
- Execution Contract uses existing `MissionSpec`, `WorkContract`, `ChiefBrainKernel.submit` and `KernelExecutionGuard`; compiler/approval must be actual trusted runtime actions, not model-supplied booleans.
- Contract **mission_id** is distinct from cognitive proposal **proposal_id**; use `WorkContract.provenance = proposal_id` and `KernelAdmissionContext.metadata.contract_id = WorkContract.contract_id` to bind the exact approved contract. For real production use, the trusted controller must additionally enforce workspace, allowed actions, budget, model cost, execution identity and lease **at actual tool/OS boundary**. This temporary in-process binding is **not a sandbox, authorization oracle, or cryptographic signature**.
- OpenMausBot `REPORTED` reflects its runtime. It is not accepted QA or learned experience. Child tree and real test process exit receipts are independently needed.
- Learning requires immutable evidence provenance, applicability and contraindications, retrieval, actual use on unseen Task B and a no-memory control. No measured tokens means `NOT_VERIFIED`, not zero.
- One durable cognitive owner, one writer per resource; default L0 deterministic, L1 single Worker, L2 sequential Researcher→Engineer→Independent QA. L3 concurrency only after measured benefit.

## Five memory views over existing storage

Episodic, Semantic, Procedural, Causal, and Self Model are logical views, **not five new databases**. Include source, confidence, hypotheses vs verification, applicability, counterexamples, invalidation/supersession, version and verified outcome. Context Compiler selects evidence-linked minimal task-relevant state; never inject unbounded history or all Skills.

## Correctness requirements / proof obligations

1. **Cognition is free; side effects are not.** A model-written status/flag cannot grant external execution.
2. **No false completion.** Job `completed` means an execution report only; protected QA decides acceptance and learning.
3. **No false trust in hash.** SHA-256 proves byte equality, not who ran a test.
4. **Recover without exactly-once fantasy.** Persist mission/attempt/epoch, dedup sends and inspect uncertain external side effects before retrying.
5. **No hidden billing.** Configured provider ≠ zero cost. Missing authoritative price/available credits means block possible paid calls.
6. **No prompt-only policy.** Skills/Markdown guide behavior; OS isolation and trusted tool gateway enforce reality.
7. **No authority inflation from tests.** Fake CLI, synthetic fixtures and GitGuardian are supporting evidence, never true OpenMausBot three-agent PASS.

## Current code-based gaps (2026-11-08, not completion claims)

- **G1:** Cognitive proposal → controlled WorkContract/Kernel admission lacked enforcement at `ExecutionProof.submit_proposal()`. Addressed as a **fail-closed adapter entry change in this isolated branch**; actual production controller wiring and OS tool policy remain unproven.
- **G2:** `AutonomousGoalLoop` currently emits only two fixed read-only intent categories; real synthetic repair requires an independent mission compilation step and actual lab authority, not implicit upgrade of R0.
- **G3:** AEP-02 SQLite correlation ledger is an isolated lab ledger; canonical mission-store integration remains outstanding. Avoid a second production ledger.
- **G4:** Cross-task verified experience in actual `MemoryController` and Task B transfer is unproven; PR #54 and PR #57 memory must be mapped before coding a duplicate store.
- **G5:** Mac owner's latest preflight reports OpenMausBot 0.1.148 online but repo path broken, two historical PR objects absent and model costs unverified; fresh isolated clone + Python >=3.12 required before live tests. No real three-agent run accepted.

## Capability metric contracts

| Metric | Formula / evidence | Guardrail |
|---|---|---|
| Independent acceptance rate | independently accepted missions / all eligible attempted missions | log failures/uncertain/blocked separately; don't filter denominator to successes |
| Validated new-task transfer | accepted unseen tasks with recorded applied verified memory / eligible unseen memory trials; compare to isolated no-memory group | same test suite and resources, report sample sizes and uncertainty |
| Verified capability growth | improvement in held-out task acceptance or quality at a fixed cost/risk budget across repeated trials | retain old-suite performance; refuse gains bought by unsafe permissions |
| Cost per accepted result | independently measured provider spend / accepted tasks | missing bills = NOT_VERIFIED, never zero |
| False success rejection | rejected forged/old/incomplete receipts / injected invalid receipts | independent verifier; source and task ID provenance |
| Recovery success | correctly resumed tasks with no extra side effects / intentionally interrupted eligible tasks | process and machine reboot measured separately |

Baseline targets require real repeated trials. A single synthetic success is only a protocol proof.

## Phase order / checkpoints

**P0:** Native Mac full SHA test baseline for #53/#54/#55/#57/#58/#59 + CLI and free-model truth. **P1:** Real AEP-03 three-agent synthetic repair / independent QA / recover. **P2:** Canonical cognitive-to-execution contract and no duplicate scheduler. **P3:** Task A→B memory transfer and wrong-memory refusal. **P4:** calibrated self evaluation / Capability Profile. **P5:** independent Skill candidate holdout experiments / safe rollback. **P6:** long-running and multi-device autonomy only after separate tests and explicit service authorization.

## GitHub branch integration rule

Preserve independent Draft PRs #53/#54/#55 and stacked #57→#58→#59. New V3 adapter work is in an isolated branch based on #59, and must stay Draft; never merge main or rewrite already-owned local Mac results. Native Mac PR regression, real OpenMausBot, model spend and independent QA must be observed rather than inferred from branch metadata.

## Skills / ordinary ChatGPT protocol

DISCOVER→READ→VERIFY→USE→EVIDENCE→REVIEW. The owner's personal ChatGPT Skills may not appear as callable plugin skills. Record `SKILL_ACCESS_BLOCKED` rather than invent contents. Save reproducible tool and commit evidence; use incremental searches, minimal per-Agent context and pinned SHAs. Chat itself is not an asynchronous worker or permanent long-term memory system.
