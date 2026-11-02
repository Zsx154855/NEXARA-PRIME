# Product contract — external product (v0, for owner approval)

Status: **DRAFT — requires an owner decision** (it contradicts the current identity contract).

## 1. What the conflict is

`contracts/nexara/NEXARA_IDENTITY_CONTRACT_V1.json` states:

- `:18` "A first-party, single-owner sovereign AI runtime … **Not a SaaS, not a platform,
  not a multi-tenant service.**"
- `:27` `"owner_type": "single_owner"`
- `:31` `"authority_model": "owner_only"`
- `:59` "NEXARA shall NEVER be positioned as a public platform, multi-tenant service, SaaS,
  or community project."

Choosing "external product" therefore is not a feature decision — it **amends a frozen
constitutional contract**. That amendment is the owner's call; nothing else in this
document is valid until it is made.

## 2. What "external product" means concretely

A different person can install it, create an account, run a mission, and trust the result
without you on the call.

| Capability | Why it is required | Current state |
|---|---|---|
| Identity (sign-up, sign-in, sessions) | otherwise anyone with the URL is the owner | none — API has no user model |
| Tenant isolation (data, workspace, evidence) | one user must not read another's missions | none — single SQLite file, single workspace root |
| Authorization (roles, per-tenant policy) | R0–R4 assumes a single approver | single `owner_only` model |
| Deployment (container, config, health, upgrade) | a stranger must self-host | scripts assume macOS + local paths |
| Observability (logs, metrics, alerting) | support without your laptop | telemetry counts only |
| Release discipline (versioned artifacts, SBOM, migration) | trust | `dist/` gitignored, no artifacts in repo |
| Support & security process (advisories, SLA) | liability | none |

## 3. What must NOT be lost in the pivot

The existing guarantees are the product's differentiator; a SaaS that drops them is
just another agent wrapper:

- every state transition emits an event and evidence artifact;
- completion requires E1/E2 evidence, not a model's claim;
- R0–R4 approval gating and single-writer lease;
- crash-recoverable, idempotent execution;
- citations in reports resolve to real file/line (this branch).

## 4. Acceptance for v0 of the external product

1. A second person, on a clean machine, can run the documented install in ≤15 min.
2. Two accounts on one instance cannot see each other's missions (test proves it).
3. An unauthenticated request cannot create, approve or run anything (test proves it).
4. A mission's report is reproducible: same input → same cited facts.
5. A failed upgrade can be rolled back with a documented command.

## 5. Explicit non-goals for v0

- billing, quotas, marketplace, plugins, multi-region, SSO/SAML;
- migrating the macOS sandbox story; v0 targets Linux containers;
- re-architecting the kernel; the runtime stays a modular monolith.
