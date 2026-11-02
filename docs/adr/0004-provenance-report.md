# ADR 0004 — Reports carry falsifiable facts

Status: accepted (2026-11-02)

## Context
The execution stage rendered `{task}` + `{model_text}` into a template, and
verification only checked file size and sha256. "Mission completed" therefore
proved nothing about the work.

## Decision
`provenance_engine` derives facts (module count, largest file, TODO markers,
declared dependencies, test functions), each citing `path:line`. Verification
re-opens every citation. An explicit `source_dir` with no readable files blocks
the mission instead of producing an empty report.

## Consequences
Reports are checkable without a model. Provider output is kept as a separate
section and cannot masquerade as evidence.
