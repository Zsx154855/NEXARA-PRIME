# NEXARA Sovereign Engineering Constitution (NSEC) V1 — SUPERSEDED

**Canonical ID:** `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1`
**Status:** SUPERSEDED by [NSEC V2.1](NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md) as of 2026-07-18
**Authority Level:** SUPREME (historical — NEXARA authority transferred to NSEC V2.1 per 2026-07-18 upgrade; this document is immutable and retained for audit trail only)
**Ratified:** 2026-07-18
**Superseded:** 2026-07-18
**Reason:** Per human directive: V2.0 expands V1 from 17 English Articles to 19 Chinese Chapters (55 Articles). Full migration table in V2.0 Appendix A.
**Preserved For:** Complete audit trail. This file remains immutable — no further edits permitted.
**Successor:** governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md

---

## Preamble

This document is the single highest engineering governance source for the NEXARA PRIME project. Every agent, script, CI pipeline, skill, contract, policy, and human contributor operates under its authority. No other document, convention, model output, or runtime behavior may contradict it. When any conflict is discovered, this Constitution prevails and the conflicting artifact must be corrected.

This Constitution is **sovereign** — it is owned by the project, stored in its repository, and enforceable by automated verification. It does not depend on any external service, model provider, or platform for its authority.

---

## Article I — Fixed Engineering Mainline

### I.1 Single Mainline

The project has exactly one engineering mainline: the `main` branch of `Zsx154855/NEXARA-PRIME`. All work traces to this mainline. No fork, mirror, or derivative may claim mainline authority without an explicit ADR and human approval.

### I.2 Mainline Stability

`main` must never be broken. Every commit to `main` must pass all tests, static checks, secret scans, state drift detection, and governance validation. A broken `main` is a CRITICAL incident and must be resolved before any other work proceeds.

### I.3 Optimal Direction First

Before any implementation, the optimal direction must be determined through weighted multi-criteria analysis. No work begins without a clear rationale for why the chosen approach is superior to viable alternatives.

### I.4 Alternative Comparison

For any non-trivial decision, at least two alternatives must be evaluated against the same weighted criteria. The evaluation must be recorded. Defaulting to the first idea or the most familiar pattern without comparison is prohibited.

---

## Article II — Maximum Reachable Endpoint

### II.1 Complete Before Partial

Every task must aim for the maximum reachable endpoint within its authorized scope. Artificially stopping at an intermediate milestone when more could be completed safely and correctly is prohibited.

### II.2 No Artificial Splitting

Work must not be split into multiple small PRs, commits, or missions to create an appearance of velocity or to avoid difficult integration. A single coherent change must be delivered as a single coherent unit.

### II.3 Complete, Unsplit Delivery

When a task can be completed in one pass without violating safety, quality, or scope boundaries, it must be completed in one pass. Multi-pass delivery of what could be a single pass is waste.

### II.4 Context Integration

All relevant context — code, tests, reviews, state, evidence, prior failures — must be gathered before implementation begins. Piecemeal fixes based on partial context are prohibited.

---

## Article III — Contract First

### III.1 Contract Before Implementation

Every interface, API, state transition, and data format must have a defined contract before implementation. The contract specifies inputs, outputs, error modes, and compatibility guarantees. Implementation follows contract, not the reverse.

### III.2 Schema-Enforced

Contracts must be machine-validatable where feasible (JSON Schema, YAML with validation, typed Protocol classes, OpenAPI). Human-language-only contracts are acceptable only when machine validation is genuinely infeasible.

### III.3 Compatibility

Contract changes must declare backward compatibility impact. Breaking changes require an ADR, a migration plan, and a deprecation period proportional to the blast radius.

---

## Article IV — Root Cause Repair

### IV.1 Root Cause, Not Symptom

Every defect must be traced to its root cause. Fixes must address the root cause, not mask the symptom. Symptom-only fixes create technical debt and must be explicitly logged with a remediation plan.

### IV.2 Clustered Resolution

Defects sharing a common root cause must be resolved in a single batch. Fixing one instance while leaving others with the same root cause is prohibited.

### IV.3 No Test-Massaging

Tests must not be weakened, removed, or rewritten to accommodate incorrect implementation. If a test fails, either the implementation is wrong or the test is wrong — determine which and fix the right one. Never change an assertion just to make CI green.

---

## Article V — Architecture Stability

### V.1 Stable Core

The architectural core — runtime kernel, state management, evidence chain, security primitives, governance contracts — must remain stable. Changes to the core require an ADR, multi-perspective review, and full regression testing.

### V.2 Layered Design

Changes must respect layer boundaries. A capability layer change must not require kernel changes unless the capability is genuinely impossible within existing kernel interfaces. Cross-layer leakage is a design defect.

### V.3 No Second System

The project must never create a second scheduler, second approval queue, second evidence store, second state system, second truth source, second CLI, second recovery engine, or second policy engine. If a capability is needed, it extends the existing system or replaces it completely with a migration — never runs alongside as a duplicate.

---

## Article VI — Technical Debt Management

### VI.1 Debt Is Recorded

All technical debt must be explicitly recorded with: location, nature, impact, remediation plan, and estimated effort. Undocumented debt is prohibited.

### VI.2 Debt Must Not Accumulate

Every change must leave the codebase at least as clean as it found it. If a change touches code with existing debt, the debt must be addressed or explicitly deferred with a recorded reason. "It was already messy" is not a valid reason to add more mess.

### VI.3 Quality Must Not Degrade

No change may reduce test coverage, weaken static analysis, bypass security checks, or degrade performance below established baselines. Quality metrics are ratcheted: they only go up.

---

## Article VII — Engineering Honesty

### VII.1 Facts First

Engineering decisions must be based on verified facts: test results, measurements, logs, and reproducible evidence. Intuition, preference, and authority have their place in strategy — they do not override measured reality.

### VII.2 Single Truth

Every fact has exactly one canonical representation. Test results live in test reports, not in chat transcripts. State lives in `.nexara/`, not in a model's context window. Git HEAD is the authoritative code version — verbal descriptions of "what the code does" are not.

### VII.3 No Reinvention

Before building anything, search for existing implementations: in this repository, in the ecosystem, in open source. If a battle-tested solution exists and meets requirements, adopt or adapt it. Building from scratch requires explicit justification.

---

## Article VIII — Lifecycle Responsibility

### VIII.1 Own What You Build

Every component must have a clear owner responsible for its full lifecycle: design, implementation, testing, deployment, monitoring, failure recovery, and eventual deprecation. Orphaned components are technical debt.

### VIII.2 Evolution Over Replacement

Prefer evolving existing components over replacing them. Replacement is justified only when evolution is genuinely infeasible — not merely inconvenient. Every replacement must include a migration path and rollback plan.

### VIII.3 Long-Term Value Maximization

Optimize for long-term project value, not short-term velocity. A solution that takes twice as long but eliminates a class of future problems is preferred over a quick fix that guarantees recurring issues.

---

## Article IX — Uncertainty Disclosure

### IX.1 Declare Uncertainty

When a decision must be made without complete information, the uncertainty must be explicitly declared: what is unknown, what assumptions are being made, what the confidence level is, and what would change the decision if known.

### IX.2 No False Certainty

"Do not use language that implies certainty when uncertainty exists." Banned phrases include: "should be fine," "probably works," "looks correct," "theoretically complete," "basically done."

### IX.3 Reversible When Uncertain

When uncertainty is high, prefer reversible decisions. An irreversible decision under high uncertainty requires explicit human approval at R3 or above.

---

## Article X — Execution Priority and Hard Boundaries

### X.1 Execute, Don't Narrate

The default mode is execution, not narration. Describe what will be done only when human approval is required before action. Otherwise: audit, plan internally, execute, verify, report.

### X.2 Few But Hard Boundaries

The project has few rules, but they are hard. The hard boundaries are: no push/merge/tag/release/deploy without human approval, no secret leakage, no destructive operations without confirmation, no test-weakening, no second-system creation, no mock-as-real.

### X.3 Continuous Progress

Between hard boundaries, execution is continuous. Each completed unit of work flows directly into the next without waiting for permission, narration, or handoff. The Program Loop does not stop at local milestones.

---

## Article XI — Human Final Control

### XI.1 Human Sovereignty

The human owner retains final authority over: goals, approval, pause, takeover, revocation, rollback, and irreversible external actions. No agent, script, or automated system may remove or circumvent these controls.

### XI.2 Approval Gates

Push, merge, tag, release, deploy, payment, external send, secret write/rotation, sudo, and irreversible deletion require explicit, current human approval. Prior approval does not carry forward to new actions. Ambiguous approval does not count.

### XI.3 Human-Readable State

All program state must be human-readable and human-verifiable. Binary blobs, opaque serialization, and model-internal representations are not acceptable as canonical state.

---

## Article XII — Multi-Agent Single Writer

### XII.1 One Writer Per Workspace

At any moment, exactly one agent may write to a given workspace, resource, or state file. Multiple readers are permitted. Multiple writers on the same resource is a governance violation.

### XII.2 Dynamic Specialization

Agents are spawned dynamically based on task needs, not from a fixed roster. Each agent receives the minimum context needed for its role. Agents are tools, not team members — they do not persist beyond their task.

### XII.3 No Performative Multi-Agent

Spawning multiple agents solely to demonstrate multi-agent capability is prohibited. Every agent must have a clear, necessary function that cannot be fulfilled by the primary controller.

---

## Article XIII — Evidence

### XIII.1 Evidence Required

Every significant action — test run, build, state change, approval decision, merge, release — must produce verifiable evidence. Evidence includes: command executed, exit code, output summary, timestamp, environment, and git context.

### XIII.2 Evidence Is Immutable

Once recorded, evidence must not be altered, deleted, or overwritten. Corrections append, they do not replace. The evidence chain must be independently verifiable.

### XIII.3 Evidence Must Match Reality

Evidence that does not reflect what actually happened is fraud. Mock results must be clearly labeled as mock. Not-executed must be labeled as not-executed. Historical results must not be presented as current.

---

## Article XIV — Receipt

### XIV.1 Every Action Has a Receipt

Every state-changing operation produces a receipt containing: operation identity, inputs (by hash), outputs (by hash), timestamp, actor, and trace. Receipts chain: each receipt references the previous receipt's hash.

### XIV.2 Unified Hash Contract

All receipts use the project's single Receipt Hash Contract: `hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()`. No second hash algorithm, no custom digest format, no ad-hoc checksum.

### XIV.3 Receipts Are Verifiable

Any receipt can be independently verified by re-computing its hash from the referenced inputs. A receipt that cannot be verified is invalid. Verification must not require access to external services.

---

## Article XV — Complete Delivery Responsibility

### XV.1 Deliver Complete

Every task delivers a complete, working, tested, evidenced, and documented result. "The code is written" is not delivery. Delivery means: code + tests + evidence + state update + passing CI + clean worktree.

### XV.2 No Handoff Without Evidence

Work must not be handed off to another agent or to the human without complete evidence of what was done, what was verified, what failed, and what remains.

### XV.3 PR Ready

The target state for every development branch is PR Ready: all tests pass, all checks pass, evidence is complete, diff is clean, scope matches, and no unrelated changes are present.

---

## Article XVI — Amendment Procedure

### XVI.1 Amendments Require ADR

Any change to this Constitution requires an Architecture Decision Record (ADR) documenting: the proposed change, the rationale, alternatives considered, impact analysis, and migration plan.

### XVI.2 R4 Classification

Constitution amendments are classified R4 (Critical/Release). They require: program lead approval, maintainer approval, release manager approval, security review, and full regression testing.

### XVI.3 Versioning

This Constitution follows semantic versioning for its identity (`V1`, `V2`, ...). Major version changes require all subordinate documents to re-declare their compliance. Minor clarifications that do not change principles do not require a version bump.

---

## Article XVII — Interpretation

### XVII.1 Literal Priority

When interpreting this Constitution, the literal text takes priority over intent, spirit, or convention. If the text is ambiguous, an ADR must clarify it. Agents must not "interpret" ambiguity to justify violating a clear principle.

### XVII.2 Conflict Resolution

When this Constitution conflicts with any other document, contract, policy, or model output:
1. This Constitution prevails.
2. The conflicting artifact must be corrected or deprecated.
3. If the conflict reveals a genuine error in this Constitution, it must be amended per Article XVI — but the existing text remains authoritative until the amendment is ratified.

### XVII.3 Reality Override

Verified facts override any document, including this Constitution. If reality (measured test results, git state, file contents, runtime behavior) contradicts a documented claim:
1. Reality is correct.
2. The document must be updated to match reality.
3. If the document is this Constitution, an amendment is required — but the fact remains true in the meantime.

This is the **Reality First** principle: documents describe reality; they do not create it.

---

## Signatures

| Role | Actor | Date |
|------|-------|------|
| Program Lead | Human Owner | 2026-07-18 |
| Ratification | NEXARA NSEC Governance Baseline V1 Mission | 2026-07-18 |

---

## Appendix A — Core Principles Index

| # | Principle | Article |
|---|-----------|---------|
| 1 | Fixed Engineering Mainline | I |
| 2 | Mainline Stability | I.2 |
| 3 | Optimal Direction First | I.3 |
| 4 | Alternative Comparison | I.4 |
| 5 | Maximum Reachable Endpoint | II |
| 6 | No Artificial Splitting | II.2 |
| 7 | Complete Unsplit Delivery | II.3 |
| 8 | Context Integration | II.4 |
| 9 | Contract First | III |
| 10 | Root Cause Repair | IV |
| 11 | Architecture Stability | V |
| 12 | Technical Debt Management | VI |
| 13 | Quality Must Not Degrade | VI.3 |
| 14 | Engineering Honesty | VII |
| 15 | Facts First | VII.1 |
| 16 | Single Truth | VII.2 |
| 17 | No Reinvention | VII.3 |
| 18 | Lifecycle Responsibility | VIII |
| 19 | Main-Brain Thinking (Long-Term Value) | VIII.3 |
| 20 | Uncertainty Disclosure | IX |
| 21 | Execution Priority, Few But Hard Boundaries | X |
| 22 | Human Final Control | XI |
| 23 | Multi-Agent Single Writer | XII |
| 24 | Evidence | XIII |
| 25 | Receipt | XIV |
| 26 | Complete Delivery Responsibility | XV |
| 27 | Reality First Override | XVII.3 |

## Appendix B — Prohibited Practices

1. Creating a second scheduler, approval queue, evidence store, state system, truth source, CLI, recovery engine, or policy engine.
2. Shipping code without tests, evidence, and state update.
3. Weakening tests to achieve PASS.
4. Presenting mock/dry-run as live/verified.
5. Using banned certainty-evasion phrases ("should be fine," "probably works," "basically done").
6. Hardcoding secrets, tokens, or credentials.
7. Deleting or overwriting evidence.
8. Spawning agents without clear necessary function.
9. Building from scratch without searching for existing solutions.
10. Merge/push/tag/release/deploy without explicit human approval.
11. Artificially splitting coherent work across multiple PRs.
12. Creating a second document claiming supreme governance authority.
