# ADR-008: Brain memory on the canonical SQLiteStore

- Status: Proposed (P2, not wired into Runtime)
- Date: 2026-11-15
- Owners: platform + memory
- Baseline: `work/task3-receipt-binding-20261114@7a9291e` + local adapter commit

## Context

`BrainDB` defaults to `.nexara/brain_state.db` (`src/nexara_prime/brain/db.py:24`),
while the Runtime opens `Settings.db_path` (`NEXARA_DB_PATH`, default
`runtime/nexara.db`) as `SQLiteStore` (`src/nexara_prime/runtime.py:248`).
Wiring `MemoryController(BrainDB())` into `ChiefBrainKernel` would therefore
create a second SQLite authority and two independent migration/backup surfaces.

## Decision

Allow `BrainDB(path=None, *, store=SQLiteStore)` to run on an injected
canonical store. The adapter reuses the existing connection/lock and only adds
the brain tables (`_BRAIN_DDL`) to that store. Path is derived from the store;
a caller-supplied conflicting path raises `brain_store_path_mismatch`.
Production Runtime wiring is intentionally **not** changed in this ADR; the
kernel still receives no memory controller.

## Consequences

- One path, one connection pool, one backup/migration surface when wired.
- `BrainDB` retains its legacy default for tests and standalone use.
- Runtime integration remains blocked on the product decision about whether
  brain memory belongs in `nexara.db` or a separate attached database; that
  decision is required before `runtime.py:140-151` changes.

## Verification

`tests/brain/test_memory_authority.py` proves the injected store is reused
(`brain._conn is store._conn`), memory round-trips, and no `.nexara/` file is
created. Isolated only: temporary directories, no production DB.
