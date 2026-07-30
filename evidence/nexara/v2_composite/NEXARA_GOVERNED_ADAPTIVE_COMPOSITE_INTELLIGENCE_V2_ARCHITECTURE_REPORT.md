# NEXARA Governed Adaptive Composite Intelligence V2 — Architecture Report

**Generated:** 2026-07-30T16:55:24.133780Z
**Branch:** work/nexara-governed-adaptive-composite-intelligence-v2
**Head:** 859a8bdc24811c7bbea401bb23a99433bddfecbd
**Base (PR34):** aea49f4ab812eb54936dea459c0bffc607f96b69
**Tree SHA:** d7f8450b4d1065131aada8999b43ed5bebf000be
**Source Candidate:** e5ff0e8

## Architecture Overview

The V2 Composite Intelligence system adds a governed, adaptive model routing layer
above the existing ModelRouter. It introduces 7 new modules and 1 modification:

### New Modules

| Module | Lines | Contract | Purpose |
|--------|-------|----------|---------|
| model_portfolio_registry.py | 185 | MODEL_PORTFOLIO_REGISTRY_CONTRACT_V1 | Provider health registry with production/mock separation |
| mission_intelligence_profiler.py | 170 | MISSION_INTELLIGENCE_PROFILE_CONTRACT_V1 | Mission complexity/risk profiling → tier routing |
| knowledge_anchor.py | 138 | KNOWLEDGE_ANCHOR_CONTRACT_V1 | Immutable knowledge anchor with provenance |
| dynamic_prompt_builder.py | 121 | DYNAMIC_PROMPT_PACKAGE_CONTRACT_V1 | Deterministic prompt building with hash reproducibility |
| composite_orchestration.py | 181 | COMPOSITE_ORCHESTRATION_CONTRACT_V1 | Council/verifier/pro routing orchestration |
| model_evaluation.py | 164 | MODEL_EVALUATION_CONTRACT_V1 | Schema/contract violation detection |
| governed_reroute.py | 142 | GOVERNED_REROUTE_CONTRACT_V1 | Reroute attempt limiting with escalation |

### Modified

| Module | Lines | Contract |
|--------|-------|----------|
| model_router.py | 377 (+61) | MODEL_ROUTING_CONTRACT_V2 — V2 opt-in path |

### Evidence Schemas (Inline)

| Schema | Location |
|--------|----------|
| MODEL_INVOCATION_EVIDENCE_SCHEMA_V1 | model_evaluation.py → evaluate() result |
| MODEL_ROUTING_RECEIPT_SCHEMA_V1 | governed_reroute.py → RerouteRecord |

## Design Principles

1. **Mock never in production** — registry.list_production() excludes mock entries
2. **Fail-closed** — no real providers → no routing (not fallback to mock)
3. **Opt-in V2** — ModelRouter(use_composite_v2=True), disabled by default
4. **V1 compatibility** — existing callers unaffected
5. **Immutable anchors** — Soul/identity cannot be overwritten
6. **Prompt injection resistance** — anchors isolated from user input
7. **Deterministic routing** — same inputs → same route
8. **Provider health** — UNHEALTHY excluded from production pool
9. **Reroute limits** — MAX_ROUTE_ATTEMPTS=3, then escalate to human
10. **Council independence** — unique provider entries, no duplicates

## Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Portfolio Registry | 3 | PASS |
| Mission Profiler | 4 | PASS |
| Knowledge Anchor | 5 | PASS |
| Prompt Builder | 3 | PASS |
| Orchestration | 4 | PASS |
| Evaluation | 2 | PASS |
| Reroute | 2 | PASS |
| V1-V2 Compat | 7 | PASS |
| **Total** | **30** | **30/30 PASS** |

## Full Suite Results

- Baseline (PR34): 1614 passed, exit 0
- Candidate: 1644 passed, exit 0
- New regressions: 0
- New tests: 30

## Quality Gates

- Ruff: CLEAN (0 errors)
- NSEC V2.1: PASS
- Secret scan: CLEAN
- P0: 0, P1: 0, P2: 0
