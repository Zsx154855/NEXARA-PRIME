# ADR 0007 — Multi-tenant deployment profile (amends the identity contract)

Status: accepted (2026-11-03), owner-authorized

## Context
`contracts/nexara/NEXARA_IDENTITY_CONTRACT_V1.json` froze the product as
single-owner and explicitly "not a SaaS". The owner has since directed a full
takeover with the goal of an **external product**, which requires identity and
tenant isolation. Leaving the contradiction in place would mean writing code
against a document that forbids it.

## Decision
- Add an **optional** deployment profile: `NEXARA_MULTI_TENANT=1`.
- The default profile stays single-owner, shell/loopback, no accounts — nothing
  changes for the current user.
- In the multi-tenant profile, every record carries `tenant_id`; authentication
  is required for all routes except `/health` and `/auth/*`.
- The forbidden framing is narrowed: NEXARA is not a public multi-tenant service
  *unless this profile is enabled by the owner*.

## Consequences
- Two code paths to test; the single-tenant path is the regression baseline.
- Tenancy is enforced at the store layer, so a forgotten filter fails closed
  (cross-tenant reads return nothing).
- Roles beyond owner/member, billing and SSO remain out of scope.
