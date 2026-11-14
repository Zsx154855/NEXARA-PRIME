# NEXARA-PRIME | R9-B2.0 canonical experience recall without verification side effects

Status: ISOLATED_CODE_COMMITTED / MAC_TEST_NOT_RUN / BUSINESS_OUTCOME_UNVERIFIED
Baseline: R9-B1 strict-readonly commit `2551a7f076ac02700481c57b954cb0418688a4a8`
Branch: `fix/pr54-r9-b2-strict-experience-recall-20261114`

## Evidence basis

- Historical R8: 30 Mac regression tests passed. This proves component behavior only; success-positive tests used injected booleans and mocked receipt interfaces.
- Historical R9-B1: 41 Mac tests passed on real local SQLite + report, explicitly mock MODEL provider, and enforced read-only receipt checking.
- Source discovery: `ExperienceStore._canonical_business_outcome_verified` still called `EvidenceStore.receipt_status(mission_id)` without read_only.
- Source discovery: `ExperienceStore.list_all()` called `MemoryController.rank_retrieve`, which always called `BrainDB.log_access` and INSERTed into `memory_access_log` despite being a trusted-success verification read.
- Thus fixing receipt_status alone cannot guarantee no SQL writes during trusted recall. Live runtime write count for this R8 path is NOT_YET_MEASURED.

## B2.0 limited repair

1. Existing `MemoryController.rank_retrieve` now accepts additive keyword `record_access=False`. Default remains `True` for normal telemetry.
2. `ExperienceStore` canonical success proof uses canonical `EvidenceStore.receipt_status(mission_id, read_only=True)`, which fails closed on not-preverified receipts.
3. `ExperienceStore.list_all()` uses `record_access=False` for persisted trusted verification; it does not write access telemetry while examining success evidence.
4. `MemoryRetrievalAdapter.retrieve(..., read_only=True)` allows a caller to audit retrieval without access log writes; default remains logged as previously.
5. R7/R8 old test doubles for receipt_status updated to accept new kwargs only; all existing ASSERT expressions remain unchanged. **Test blobs changed**. No attempt to claim byte-identical regression tests.
6. New targeted QA `tests/test_r9_b2_experience_read_only.py` checks real evidence and brain SQLite connections with independent SQLite write-denial authorizers, revoked/extra unverified receipt quarantine, and default access logging backward-compatibility.

## Real code task A: independent outcome acceptance requirements (NOT DONE)

Candidate deliverable is this precise R9-B2 strict-readonly code change, not an arbitrary "report generated" task.

Independent QA must, in a distinct trusted execution environment:
- Fetch this branch at exact pinned HEAD and inspect its code diff vs B1.
- Confirm the original R8 (30), B1 (11) and new B2 tests pass with actual Mac sandbox execution, no paid model.
- Verify real Git HEAD, clean worktree, test logs, test run command and tool exit codes.
- Re-run a holdout with read-only authorization on both DB connections and a tampered receipt case.
- Ensure implementation and independent tester have independent identity and write authority; local `actor='reviewer'` labels are not sufficient.
- Produce an authenticated verdict tied to Mission ID, its actual WorkContract acceptance criteria, immutable source SHA, artifact SHA256, test command, exit code, evidence IDs and independent verifier identity.

Until this independent verdict is verifiably bound to the existing Mission/Evidence/Receipt authority, **DO NOT** pass any successful result to `ExperienceStore.outcome_validator`. A local test callback returning True only exercises dependency wiring; no BUSINESS_SUCCESS yet.

## Required Mac Gate

- Exact ref pin + isolated worktree + no model API/production writes.
- New B2 tests: 3.
- Original B1 tests: 8 plus B1 independent QA: 3 (11).
- R8 4 suites: 9 + 17 + 2 + 2 (30).
- Expected tests: 44 total, *not run yet*.
- Assert dual SQLite total_changes unchanged during canonical trusted retrieval, while regular logged rank_retrieve still produces access logs.
- Audit the one-arg receipt test mock compatibility adaptation (no assert changes).
- End with HEAD + exit codes + clean worktree; assign PASS only from actual execution.

## Limitations, not to be mistaken for gate passes

- `read_only=True` on MemoryRetrievalAdapter is optional; normal reasoning retrieval intentionally records access telemetry. This subgate only proves a strict read-only opt-in path and canonical ExperienceStore behavior.
- `outcome_validator=lambda True` in targeted B2 tests is an explicit **test seam**; the real independent outcome validator remains NOT_CONNECTED.
- No real independent QA attestation, no authenticated agent identity, no Mission A->B knowledge-transfer behavior, no real Mac Relay autonomy, no production acceptance.
- No global memory architecture migration, no approval system addition, no change to R8 evidence identity criteria, no main merge.

Gate: R9_B2_0_CODE_COMMITTED / MAC_RUN_PENDING / INDEPENDENT_QA_PENDING.
