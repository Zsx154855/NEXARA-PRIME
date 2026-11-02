# ADR 0003 — Sandbox backends fail closed

Status: accepted (2026-11-02)

## Context
`MacOSSandboxBackend.probe_capability()` claimed `workspace_jail` on non-Darwin
systems while `execute()` had no such implementation. Tests asserted the claim.

## Decision
- One selector: macOS `sandbox-exec` when present; otherwise `UnavailableSandboxBackend`.
- A process backend exists but is opt-in (`NEXARA_SANDBOX_ALLOW_PROCESS_FALLBACK=true`)
  and reports `process_restricted`, never `workspace_jail`.
- A denied/unavailable sandbox never silently degrades to plain execution.

## Consequences
Linux defaults to "cannot execute sandboxed commands" rather than "pretends to".
Operators can opt in with a weaker, honestly-labelled mechanism.
