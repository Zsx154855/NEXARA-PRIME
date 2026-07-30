# NEXARA Model Portfolio Security Report

**Generated:** 2026-07-30T16:55:24.133780Z
**Head:** 859a8bdc24811c7bbea401bb23a99433bddfecbd

## Security Analysis

| Check | Result |
|-------|--------|
| Mock in production | PASS — registry.list_production() excludes mock |
| Fail-closed | PASS — no real providers → no routing |
| Prompt injection | PASS — anchor immutable tier cannot be overwritten |
| Secret redaction | PASS — provider format excludes API_KEY/sk- patterns |
| Token budget | PASS — immutables survive budget squeeze |
| Approval bypass | PASS — owner_approval → verifier mode |
| Reroute DoS | PASS — MAX_ROUTE_ATTEMPTS=3 limit |
| Council isolation | PASS — unique entries, no duplicates |
| Secret scan | CLEAN — 0 hardcoded secrets |
| NSEC governance | PASS — all integrity checks passed |

## Contract Enforcement

| Contract | Enforced By |
|----------|-------------|
| MODEL_PORTFOLIO_REGISTRY_CONTRACT_V1 | ModelPortfolioRegistry.list_production() |
| MISSION_INTELLIGENCE_PROFILE_CONTRACT_V1 | MissionIntelligenceProfiler.profile() |
| KNOWLEDGE_ANCHOR_CONTRACT_V1 | KnowledgeAnchor.add() — IMMUTABLE rejection |
| DYNAMIC_PROMPT_PACKAGE_CONTRACT_V1 | DynamicPromptBuilder.to_provider_format() |
| COMPOSITE_ORCHESTRATION_CONTRACT_V1 | CompositeOrchestrationEngine.route() |
| MODEL_EVALUATION_CONTRACT_V1 | ModelEvaluationEngine.evaluate() |
| GOVERNED_REROUTE_CONTRACT_V1 | GovernedRerouteController.may_reroute() |
| MODEL_ROUTING_CONTRACT_V2 | ModelRouter v2_enabled path |

## Threat Model Coverage

- **Production leak**: mock excluded from production candidates
- **Fail-open**: provider exhaustion → fail-closed (no routing)
- **Prompt injection**: anchor immutability + separate storage
- **Secret leak**: provider format doesn't include raw keys
- **Reroute flood**: 3-attempt limit with human escalation
- **Council collusion**: single-provider cannot form council
