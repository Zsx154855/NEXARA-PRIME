# ADR 0001 — SQLite WAL and busy timeout

Status: accepted (2026-11-02)

## Context
The runtime is opened by the API, the CLI and background threads at the same
time, and the product claims durability. The store used the default rollback
journal and had no `busy_timeout`.

## Decision
`journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000` on every connection.

## Consequences
- Two processes can write concurrently without `database is locked`.
- A SIGKILL mid-transaction rolls back; `integrity_check` stays `ok` (tested).
- Slightly lower write throughput; acceptable for a single-owner runtime.
