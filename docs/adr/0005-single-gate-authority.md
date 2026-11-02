# ADR 0005 — One derived gate authority

Status: accepted (2026-11-02)

## Context
Three gate files disagreed: YAML (all PASS), `GATE_STATUS.json` (all PASS while
admitting earlier false PASSes) and `PROGRAM_STATE.json` (G10 BLOCKED). A
drift checker compared two strings, never the tests.

## Decision
`scripts/governance/derive_gate_status.py` computes status from artifacts and
`--sync` writes it into all three surfaces. PASS requires evidence; missing
artifacts (e.g. `dist/`) produce BLOCKED.

## Consequences
Current derived state: G0 PASS, G1–G9 PARTIAL, G10 BLOCKED. The numbers are
worse than before and true.
