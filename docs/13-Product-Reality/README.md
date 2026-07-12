# NEXARA Sovereign Product Reality Engine V2

> Status: CLEAN REBUILD — additive foundation, review-gated.

## Purpose

The Sovereign Product Reality Engine (SPRE) is the governed product-reality plane above NEXARA Design OS. It maintains an evidence-backed digital twin of product intent, experience semantics, implementation, runtime truth, human control, telemetry, and controlled evolution.

NEXARA PRIME remains the sovereign runtime kernel. Design OS remains a subsystem. Figma, SwiftUI, Web, Canva, and future visionOS surfaces are projections of one product reality, not independent sources of truth.

## V2 security corrections

V2 is rebuilt from a clean revert baseline and incorporates all post-merge Codex findings from V1:

1. Every promotion requires real, digest-verified Evidence bound to the same mission.
2. R3/R4 approval must be loaded from the persistent ApprovalEngine, match mission and exact proposal action, remain unexpired, and be consumed for single-action scope.
3. Product Twin drift records preserve the difference between an absent field and a present field whose value is null.
4. R2–R4 proposals require a rollback plan, rollback checkpoint, and verified rollback evidence.

A caller-provided string such as `human_approval_status="approved"` is not part of the V2 contract and cannot authorize promotion.

## Architecture

```text
Human Sovereignty Plane
        ↓
Product Constitution
        ↓
Experience Genome + Product World Model
        ↓
Sovereign Product Twin
        ↓
Design OS + Design Compiler
        ↓
Figma / macOS / iPadOS / iOS / Web / visionOS / Canva
        ↓
Runtime Binding + Telemetry + Evidence
        ↓
Causal Evaluation + Controlled Evolution
```

## Non-negotiable invariants

- Mission First.
- Runtime Truth cannot be replaced by optimistic UI state.
- Every verified promotion has auditable evidence.
- Consequential evolution is bound to real stored approvals.
- R2–R4 evolution has an evidenced recovery path.
- Missing and null remain semantically distinct.
- Provider identity is not product identity.
- No private chain-of-thought is exposed.
- Existing L01–L12 architecture remains fixed.

## V2 implementation boundary

V2 adds isolated contracts, registries, validation engines, and tests. It does not modify existing mission execution, ApprovalEngine, sandbox, EvidenceStore, audit chain, provider routing, secrets, or Adaptive Runtime behavior.

## Promotion action binding

Each proposal has a deterministic approval action:

```text
product_reality.promote:<proposal_id>
```

For R3/R4, the stored approval must match:

- approval status = approved;
- mission id = proposal mission id;
- action = deterministic promotion action;
- executor id, when specified;
- non-expired record;
- unused single-action scope.

## Gate sequence

1. `NEXARA_PRODUCT_REALITY_CONSTITUTION_LOCK_V2`
2. `NEXARA_EXPERIENCE_GENOME_FOUNDATION_V2`
3. `NEXARA_SOVEREIGN_PRODUCT_TWIN_V2`
4. `NEXARA_CONTROLLED_PRODUCT_EVOLUTION_V2`
5. `NEXARA_SPRE_V2_TEST_SECURITY_REVIEW_GATE`

## Merge requirements

- focused V2 tests pass;
- complete repository suite passes;
- all Codex review threads are resolved;
- CI and local evidence are attached;
- PR is explicitly marked ready only after review;
- merge must not occur before review results return.
