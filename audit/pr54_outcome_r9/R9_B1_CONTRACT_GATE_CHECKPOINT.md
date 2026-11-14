# NEXARA-PRIME | R9-B1 Report Mission Contract Gate

Status: CODE_COMMITTED / MAC_TESTS_NOT_RUN / INDEPENDENT_BUSINESS_QA_NOT_CONNECTED

## Fixed baseline

- R8: `b638948c4e815551764dae3fa281c6f6df8aefc8` (historical Mac component receipt: 30/30 PASS).
- New isolated branch: `audit/pr54-r9-b1-report-contract-20261114`.
- Original PR #54 and `main` must remain unchanged; no merge or production deployment.

## Verified existing source interfaces

- `NexaraRuntime` uses `MemoryKernel`, *not* `MemoryController`.
- The local report tool `file_write_report` has a durable tool-invocation payload, actual SHA256 of written bytes, tool receipt evidence, consumed single-action approval, and model-provider-independent file output.
- `MissionStateMachine` emits `mission.state_changed` events and bound `state_transition` evidence.
- `EvaluationEngine` persists an independently readable evaluation record, but its correctness metric is not equivalent to arbitrary business success.
- Existing `MissionCompiler` specifies exactly four process acceptance criteria. Any new/unknown contract criteria fail closed as `OUTCOME_UNKNOWN`.

## R9-B1 candidate scope

`ReportMissionContractVerifier.evaluate(mission_id, verification_evidence_id)`:

1. Reconstructs an unbroken, legal event transition chain from `Intent` to `Completed` and validates each state-change evidence binding.
2. Checks actual report file under the approved report root, tool invocation source, report bytes and digest, durable single-action approval consumption, and approval timing.
3. Uses the existing `EvidenceStore.receipt_status` authority (never invents independent receipt presence), integrity-bound report verification, reviewer/auditor verdicts, and real artifact identity.
4. Cross-checks evaluation ID and passing metrics against the canonical evaluation record.

Returns four named per-criterion booleans and one of:
- `CONTRACT_PASS`: four process criteria proven for this supported report-Mission template
- `CONTRACT_FAIL`: an authoritative check failed
- `OUTCOME_UNKNOWN`: unsupported contract or authoritative recheck unavailable

`business_outcome_verified=False` **always**. Contract process success does not prove arbitrary business result or independently authenticated Agent identity.

## Tests

`tests/test_r9_b1_report_contract_acceptance.py` currently contains 8 cases:
- positive real SQLite + real tool/approval/file/evidence report pipeline **with explicitly mocked model provider**
- cross-Mission evidence rejection
- unsupported criteria => `OUTCOME_UNKNOWN`
- report tampering => reject
- heartbeat evidence cannot replace verification report
- Mission state changed without corresponding transition chain => reject
- missing approval => reject
- invented evaluation ID => reject

The positive test uses a deterministic provider mock only to avoid paid API calls. Real workflow, Git, tool write, and verification evidence run locally; this is still NOT live 3-Agent independence nor real business acceptance. Do NOT claim tests PASS until executed on Mac.

## Important limitations

- The approval identity is anchored to existing approval-event/consumption records. Actor names are *not cryptographically authenticated human identity*.
- Existing Reviewer/Auditor verdicts concern report provenance and receipt integrity, not all user-defined acceptance goals.
- Existing `EvidenceStore.receipt_status` may invoke `verify()` internally, potentially repairing verification state; do not claim absolute zero database mutations from its transitively used API.
- The candidate does NOT change MemoryKernel/MemoryController, ExperienceStore, ReasoningKernel, Runtime, approval policy, or Mission state machine. It does NOT install/enable background services.
- Do not bind `ReportMissionContractVerifier` directly to R8 `outcome_validator` as a business verifier. R9-B2 must independently validate real acceptance criteria and identity.
- The test's local model provider is a mock. Real Mac Relay and autonomous Agent execution are NOT_VERIFIED.

## Next gates

1. Mac fixed-SHA source verification.
2. Run 8 B1 local contract tests on Mac and report exact output.
3. Run unchanged R8 suites: N01 9, R7 17, QA 2, R8 2 (30 total).
4. Independent QA must verify absence of false acceptance, correct authority/event correlation, no unexpected writes, and compatibility with actual Mission state.
5. After B1 passes, design minimal real independent **business outcome** attestation; only then consider R8 experience promotion.
