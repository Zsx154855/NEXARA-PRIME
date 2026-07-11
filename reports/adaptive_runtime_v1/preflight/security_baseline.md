# Adaptive Runtime V1 — Preflight Security Baseline

**Generated**: 2026-07-11T23:00:00Z  
**Gate**: NEXARA_PRIME_ADAPTIVE_RUNTIME_V1  
**Branch**: work/nexara-adaptive-runtime-v1  
**Base Commit**: c387ebfa4c71542e1d0ef872d382fed24bdfbadc (NEXARA_PRIME_SECURITY_RUNTIME_FINAL_V2_2)

---

## 1. Repository Identity

| Property | Value |
|----------|-------|
| Repo | /Users/agentos/NEXARA-PRIME |
| Branch | work/nexara-adaptive-runtime-v1 |
| Base Commit | c387ebf |
| Remote | github.com/Zsx154855/AgentBotOS.git |

## 2. Evidence Migration

### Source

/private/tmp/NEXARA-PRIME-security-v2-1/reports/

### Destination

/Users/agentos/NEXARA-PRIME/reports/

### SHA-256 Verification

| File | Source SHA-256 | Dest SHA-256 | Match |
|------|---------------|-------------|-------|
| provider_credential_live_acceptance_v2_1_1/acceptance_evidence.json | ae130dc7... | ae130dc7... | PASS |
| provider_credential_live_acceptance_v2_1_1/acceptance_report.md | e8522cbb... | e8522cbb... | PASS |
| production_security_runtime_acceptance_v2_1/final_acceptance_report.md | c7197d85... | c7197d85... | PASS |
| production_security_runtime_acceptance_v2_1/acceptance_evidence.json | 5eabfc63... | 5eabfc63... | PASS |

### Secret Scan

All 4 files scanned for:
- `sk-*` API keys
- Bearer tokens
- api_key assignments
- password values
- private_key blocks
- DeepSeek key values

**Result**: ALL CLEAN — 0 hits

## 3. Runtime Truth State

```
SECURITY_RUNTIME=CLOSED
LIVE_PROVIDER=VERIFIED
DEFAULT_LIVE_PROVIDER=deepseek
OPENAI=QUOTA_BLOCKED_OPTIONAL
NEXT_GATE=NEXARA_PRIME_ADAPTIVE_RUNTIME_V1
```

## 4. Worktree Status

- Modified: `src/nexara_prime/api.py` (from knowledge_universe gate)
- Untracked: knowledge_universe files (from prior gate)
- No unknown user modifications

## 5. Security Baseline Inheritance

All V2.1.1 security boundaries remain in force:
- Identity + Authorization
- ApprovalStore
- ToolRuntime
- MacOS Sandbox
- Workspace Jail
- NetworkPolicy (deny-by-default)
- SecretStore (macOS Keychain only)
- Security Audit Hash Chain
- EvidenceStore
- DurableRecovery

## 6. Preflight Verdict

| Check | Result |
|-------|--------|
| Repo Identity | PASS |
| Evidence Migration | PASS |
| SHA-256 Match | PASS |
| Secret Scan | PASS |
| Worktree Known | PASS |
| Security Baseline | PASS |

**OVERALL**: PASS — Proceed to Adaptive Runtime Implementation
