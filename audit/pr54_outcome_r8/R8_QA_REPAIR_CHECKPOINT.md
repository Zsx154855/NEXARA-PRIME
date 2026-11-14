# NEXARA-PRIME / PR #54 / R8 independent QA repair checkpoint

## Branch and immutable source
- Baseline: R7 `9d8b9ad8852e9a8b1c3f44fc5145c95909977795`.
- QA RED branch (never altered): `audit/pr54-r7-independent-qa-20261114`, commit `eaba713910c7818e439668273a071d9986ba8db8`.
- R8 candidate: `fix/pr54-r8-qa-recall-20261114`; see live HEAD.
- Original PR #54 `103c79f500c522492815f9b86dfa0fb80dd07e30` and main unchanged at audit start.

## Verified input (Mac terminal user report, 2026-11-14)
- R7 required component tests: original N01 9 PASS, R7 17 PASS.
- Unchanged R6 PR54 tests: 2 PASS, 1 FAIL because an old test treats a health probe as successful outcome proof. This is an intentional strict-contract change, NOT a data durability pass or a claim that all old tests pass.
- Independent QA holdout at commit `eaba713...`: **2 FAIL** on real product SQLite and real classes in Mac. No code modification by QA.

## Two R8 code repairs
1. `ExperienceStore.list_all()`, canonical **in-memory mode only**: re-check evidence and independent business acceptance on each read; revoked success is no longer returned. Legacy callback-only mode stays backward compatible and is not production assurance.
2. `MemoryRetrievalAdapter.retrieve()`: filter raw success-classified experience rows by default before supplying context to reasoning, while preserving failure/partial/blocked experiences. A canonical `ExperienceStore.list_trusted_successes()` view may be explicitly bound for validated successes. Identity of each candidate row is compared to the verified success record, preventing an unrelated memory row from reusing the experience ID.
3. The original independent QA holdout test file is copied byte-identically into R8; no assertions changed. Separate positive R8 tests confirm a trusted injection seam allows verified success and removes it on revocation, and failure context remains readable.

## Required gates; NOT yet observed at this checkpoint
- Re-run original N01: 9 expected tests, must pass unchanged.
- Re-run R7 adversarial suite: 17 expected parametrized test cases, must pass unchanged.
- Re-run original independent QA 2 holdouts on R8; both must switch RED -> GREEN.
- Run new R8 trusted recall + failure visibility 2 tests; must pass.
- Record local HEAD, Python import identity, exact exit code, clean Git worktree and per-test logs on Mac.
- The unmodified R6 success-from-heartbeat test is obsolete under the new contract. Keep failure visible separately; do not edit it to force GREEN.
- Independent QA should scrutinize direct `MemoryController.rank_retrieve()` consumers, caller-supplied validators, historical raw memory content and restart/transaction boundaries.

## Remaining explicit limitations
- **Global raw memory query quarantine NOT proven**. This R8 repair closes the actual `MemoryRetrievalAdapter` used by `ContextAssembler` but `MemoryController.rank_retrieve()` still has callers that can read raw historical experiences. Do not claim every route is safe.
- No real independent business-outcome validator is connected; R8 positive examples use **test callbacks**, not a real external QA verdict. Tests passing proves the component seam only.
- Fail closed default for reasoning may also withhold *legitimate* successful experiences until the trusted `ExperienceStore` is explicitly bound; real product integration remains incomplete.
- GitHub-hosted CI remains unavailable due to the user's GitHub billing lock.
- Mac Relay, actual 3-Agent mission, real task A-to-B outcome transfer, crash/restart and production acceptance are NOT_VERIFIED.
- No production state / paid model / main merge authorized.
