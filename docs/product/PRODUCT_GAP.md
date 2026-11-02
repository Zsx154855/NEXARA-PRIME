# Gap analysis — from current state to external product

Evidence column points at what exists today, not at intentions.

| # | Gap | Evidence today | Minimal v0 fix | Risk if skipped |
|---|---|---|---|---|
| 1 | No user identity | `api.py` has no `Depends`, no user model; auth is loopback-or-token only | users table + session cookies + sign-in route | anyone with the URL is the owner |
| 2 | No tenant isolation | one `nexara.db`, one `workspace_root` (`config.py:24-25`) | `tenant_id` on every record; per-tenant workspace root; row filter in `SQLiteStore` | cross-tenant data leak |
| 3 | Approval assumes one human | `authority_model: owner_only` | per-tenant approver role; approvals scoped to tenant | wrong person approves work |
| 4 | macOS-only execution | `sandbox_v2.py` fail-closed without `sandbox-exec` | Linux container backend (seccomp/landlock or docker) | product cannot run where users are |
| 5 | No deployment story | `scripts/run_dev.sh` assumes local paths | Dockerfile + compose + healthcheck + migration step | nobody can install it |
| 6 | No release artifacts | `dist/` gitignored; G10 BLOCKED | build wheel + container image in CI, checksums | cannot prove what you shipped |
| 7 | No observability | `telemetry.py` counts health events | structured logs + `/metrics` + error budget doc | cannot operate |
| 8 | Secret handling in tests | fixtures with dummy tokens (scanner baseline) | keep out of repo; env injection | leaks |

## Ordering constraint

Identity and tenancy (1,2) must land before deployment (5) is exposed to anyone:
shipping a single-tenant runtime to the public is worse than shipping nothing.

## First slice (proposal, one PR)

`auth + tenant column` only:

- `users` table, `POST /auth/signup`, `POST /auth/login` (argon2/bcrypt), session cookie;
- `tenant_id` column on `records`/`events` with a migration that backfills `default`;
- `SQLiteStore` requires a tenant context; cross-tenant read returns empty, not error;
- tests: two users, two missions, each sees exactly one; unauthenticated write → 401.

Explicitly *not* in that PR: container, observability, roles beyond owner/member.
