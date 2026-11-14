# NEXARA-PRIME / PR54 business-outcome admission / isolated CTO checkpoint

## Immutable source and authority
- Base: PR #54 commit `103c79f500c522492815f9b86dfa0fb80dd07e30`.
- Branch: `audit/pr54-business-outcome-admission-r1-20261114`.
- Main and original PR #54 must stay unchanged; do not merge without separate approval.
- Product: independent agent brain; NOT the film/video product.
- This is an R&D candidate, not a production-accepted business-success verifier.

## What changed
1. `ExperienceStore` uses existing `EvidenceStore.store.get_record_envelope` (the actual Mission record), `receipt_status`, existing reviewer/auditor evidence and verification evidence, not a new Mission state machine.
2. Canonical success requires Completed Mission, approved Contract with explicit acceptance criteria, evaluation_passed, verified `verification_report` linked to that Mission, verified reviewer and auditor verdicts, verifiable receipt status, and a separately injected trusted `outcome_validator`.
3. Missing or offline business verifier => fail closed with `mission_outcome_not_independently_verified`. Cross-Mission or unverified evidence => `experience_verified_evidence_required` or the strict outcome error.
4. Canonical `list_all()` rechecks the success gate on every read; old unverified canonical success rows are not deleted but excluded from `ExperienceStore` recall and statistics. Verified failure records remain readable.
5. The legacy `evidence_validator`-only constructor remains backward compatible for the nine historical N01 tests. That injected callback can authorize historical synthetic learning and MUST NOT be treated as production evidence or independently verified business success.

## Evidence versus validation status
- GitHub writes verified via the connector. This branch's real Mac pytest tests are **NOT_RUN** until logs are returned.
- GitHub Actions are blocked by an account billing lock (GitHub job annotations), so CI cannot substantiate PASS.
- Original PR #54 N01 tests: 9/9 PASS **on the unmodified PR #54 checkout**, not yet rerun on this branch.
- Original R6 PR54 tests: 2 PASS / 1 FAIL **on unmodified PR #54**. After this change, the old `test_verified_experience_is_durable_across_real_db_reopen` attempts to persist a "successful task" based solely on a health probe: its acceptance assumption is now intentionally forbidden. Run the unmodified test and log the result; do not silently weaken it. Replacement R7 tests verify failure durability and accepted-success durability separately.
- New R7 adversarial tests include *injected/stubbed* positive QA callbacks. Positive passes demonstrate only the seam, NOT real independent business QA.
- Real A→B transfer, standalone independent QA, real Mac Relay/restart recovery, full-main regression, and trusted outcome adapter remain NOT_VERIFIED.

## Required next gates
1. Run `audit/pr54_outcome_r7/run_local_mac.sh` on the authorized Mac, using only the established R6 isolated venv and Git worktree.
2. Keep the 9 original N01 assertions unchanged; report any failures exactly.
3. Run all new R7 tests; report individually. Run original R6 tests unchanged and explicitly record the one now-obsolete success-from-health-probe assumption.
4. Run a separate independent QA review and adversarial cases covering injected-validation bypass, false reviewer identity, lost receipt chain, stale Mission state, corrupted evidence, historical success recall through *other* memory APIs, and failure-recovery behavior.
5. Connect a **real trusted** independent business-acceptance authority using existing Mission/Contract/Evidence/Receipt APIs, without a new success state machine. A passed lambda-based test callback is NOT such an authority.
6. Evaluate interface/ABI compatibility, do not migrate production DB, no model calls, no new paid resource. No merge before evidence-based approval.

## Known unresolved limitations / fail-closed scope
- A Python callback injected by the host is only as trustworthy as its caller. The current candidate does NOT authenticate independent QA identity. No standalone business-verifier adapter is deployed.
- Canonical `ExperienceStore.list_all()` filters historical success; direct consumers of `MemoryController.rank_retrieve()` may still see underlying legacy rows. Whole-product quarantine is not yet proven.
- Separate BrainDB and EvidenceStore SQLite files are not one ACID transaction. Checkpoint and evidence-store recoverability under a crash are not yet proven.
- Existing runtime completion gate is NOT equivalent to independent business acceptance of individual contract criteria.
- R7 changes only isolated branch source/tests and shell runner; no actual Mac tests have been run by ChatGPT directly.
