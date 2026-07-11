# Benchmark Report

**Gate**: NEXARA_PRIME_ADAPTIVE_RUNTIME_V1
**Date**: 2026-07-11T18:42:42Z

## Scenarios (5 tasks)

1. Simple query (file read)
2. Medium refactor (multi-file code changes)
3. Complex deploy (production with rollback)
4. Audit review (security audit)
5. Fault scenario (provider failure)

## Results

### Agent Count

| Baseline | Avg Agents | Notes |
|----------|-----------|-------|
| A: Single Agent | 1.0 | Baseline minimum |
| B: Full Multi-Agent | 8.0 | Always maximum |
| C: Adaptive (Candidate) | 4.6 | Scales by complexity |

### Token Estimates

| Baseline | Avg Tokens | Notes |
|----------|-----------|-------|
| A: Single Agent | 5,640 | Baseline |
| B: Full Multi-Agent | 22,560 | 4x baseline (context duplication) |
| C: Adaptive (Candidate) | 5,640 | Token compiler active |

### Simple vs Complex Tasks

| Task Type | Adaptive Agents | Full Multi-Agent | Reduction |
|-----------|----------------|------------------|-----------|
| Simple (S0/S1) | 3.0 | 8.0 | 62.5% |
| Complex (S2/S3) | 5.7 | 8.0 | 29.2% |

### Modes Used

S0, S1, S2, S3 — all four adaptive modes exercised across 5 scenarios.

## Conclusion

Adaptive Runtime uses 62.5% fewer agents than Full Multi-Agent on simple tasks while still providing adequate agent coverage for complex tasks. Token costs are not inflated by context duplication. The system correctly scales between S0 (1 agent) and S3 (6 agents) based on complexity and risk scoring.
