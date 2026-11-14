# NEXARA-PRIME / R9-B1 strict-readonly QA repair

Status: CODE_COMMITTED, ZERO-WRITE_MAC_QA_PENDING, FULL_REGRESSION_PENDING

## Evidence prompting change (Mac / user-supplied, 2026-11-14)

- Original R9-B1 commit `fbf55311131c718d8effa0ab249d1a128f013c84` passed 8 new contract tests plus 30 unchanged R8 tests.
- Independent runtime check: `CONTRACT_STATUS=CONTRACT_PASS`, `BUSINESS_VERIFIED=False`.
- SQLite `Connection.total_changes`: 165 before evaluation, 168 after; **3 real changes**. `STRICT_READ_ONLY_GATE=FAIL`.
- GitHub source shows `ReportMissionContractVerifier.evaluate -> EvidenceStore.receipt_status -> verify_receipt_chain -> verify -> SQLiteStore.repair_record_event`; `verify()` performs SQLite updates even for already verified receipts.

## Exact repair

- New isolated branch `fix/pr54-r9-b1-strict-readonly-20261114` based on original B1 HEAD.
- `EvidenceStore.verify_receipt_chain(mission_id, *, read_only=False)` and `EvidenceStore.receipt_status(mission_id, *, tool_names=None, read_only=False)`: explicitly opt into existing read-only preverified integrity and origin-chain check `is_preverified_and_integrity_bound()` instead of repairing `verify()`.
- Default `read_only=False` retains prior EvidenceStore behavior for existing Runtime/receipts callers.
- `ReportMissionContractVerifier.evaluate` calls canonical receipt authority with `read_only=True`.
- No changes to Runtime Mission state machine, policy, R8 ExperienceStore, memory, original B1 tests, main or PR #54.

## Added independent QA (no claim of execution yet)

`tests/test_r9_b1_read_only_qa.py`:
1. Real completed Mock-provider Mission: repeat report contract check twice, require `CONTRACT_PASS` and zero SQLite changes each time.
2. Add a real persisted unverified evidence/tool pair: strict receipt chain must reject without promoting, legacy option remains repair-capable.
3. SQLite authorizer rejects all INSERT/UPDATE/DELETE during report contract verification, must report `CONTRACT_PASS` with no forbidden writes.

## Required Mac Gate

- Recheck exact Git SHA with clean detached worktree (new worktree; preserve original B1).
- Run three new independent read-only tests.
- Run original eight R9-B1 tests unchanged.
- Run unchanged R8 regression: N01 9 + R7 17 + QA 2 + R8 2.
- Check before/after `total_changes` on live test connection and Git worktree status.
- Expected total: 41 tests (3 + 8 + 30). **NOT_RUN** as of this checkpoint.

## Boundaries

- A component-level read-only check does not mean the entire application is read-only.
- `total_changes` is per connection: the SQLite authorizer test additionally catches attempted writes through that connection.
- `CONTRACT_PASS` only validates the four generic bounded-report process criteria.
- `BUSINESS_SUCCESS` remains NOT_VERIFIED; do not pass this as R8 `outcome_validator` or start self-learning.
- No paid model calls, no production edits or deployment permitted.
