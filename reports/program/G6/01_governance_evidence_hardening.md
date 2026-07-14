# G6 — Governance & Evidence Hardening

**Gate:** G6 — Governance & Evidence Hardening
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: R0-R4、E0-E2、审批绑定、审计链、secret、rollback、red-team

### Governance Matrix

| Capability | Module | Status | Tests |
|-----------|--------|--------|-------|
| R0-R4 Risk Policy | `governance.py` — PolicyEngine | ✅ | 293 |
| E0-E2 Evidence Levels | `evidence.py` — EvidenceStore | ✅ | — |
| Approval Binding | `governance.py` — ApprovalEngine | ✅ | — |
| Audit Chain | `security_audit.py` — SecurityAuditLedger | ✅ | — |
| Writer Lease | `governance.py` — WriterLeaseManager | ✅ | — |
| Secret Management | `secrets/keychain.py` + `secrets/env.py` | ✅ 0 leakage | — |
| Sandbox Enforcement | `sandbox_v2.py` | ✅ 0 escape | — |
| Rollback | `recovery.py` — DurableRecovery | ✅ no duplicates | — |
| Network Policy | `network_policy.py` — deny-by-default | ✅ | — |
| Secret Scanning | Phase 1 grep scan | ✅ 0 findings | — |

### Security Baseline (from Phase 1 verification)

| Metric | Value |
|--------|-------|
| Secret leakage | 0 |
| Approval bypass | 0 |
| Sandbox escape | 0 |
| Audit chain | intact |
| Recovery no duplicates | true |
| Hash mismatches | 0 |
| Security runtime | CLOSED |
| Hermes runtime dependency | 0 |

### Red-Team Coverage

293 governance/security tests include: approval binding, sandbox enforcement, audit persistence, network policy, secret keychain, recovery fault injection, path security (null byte rejection), and agent permission escalation prevention.
