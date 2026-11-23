# ADR 0006 — Rollback is state-only, and says so

Status: accepted (2026-11-02)

## Context
`rollback()` changed state and wrote a `rollback_point` evidence, but nothing
restored files; the surrounding docs implied more.

## Decision
The rollback evidence and `mission.result` now carry `scope: "state_only"` and
`files_restored: 0`, with a note that filesystem content is not restored.

## Consequences
The API tells the truth. A real snapshot backend is a separate, funded task.
