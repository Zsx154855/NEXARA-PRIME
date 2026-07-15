# PR #8 Post-Merge Validation — 2026-07-16 (corrected)

## Merge Details (GitHub truth)

| Field | Value |
|-------|-------|
| PR | #8 |
| GitHub mergedAt | `2026-07-15T22:26:13Z` |
| Squash merge commit | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| Full head SHA | `7407832d0e06d90a6a7a869d4aa4b1224b82b268` |
| Main local HEAD | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| origin/main HEAD | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| Branch | main |

## Working Tree

- `validation_worktree`: **CLEAN** (README.md stashed for governance validation)
- `final_user_worktree`: **PRE_EXISTING_USER_CHANGE** — README.md contains injected ID frontmatter
- README.md excluded from all PR #8 and post-merge commits

## Test Results

| Check | Result |
|-------|--------|
| Orchestration tests | 87 passed, 0 failed |
| Full test suite | 682 passed, 0 failed, 3 subtests |
| Ruff (orchestration files) | Clean |
| Secret scan | CLEAN |
| git diff --check | Clean |

## Governance (clean validation context)

```bash
git stash push -m "pre-existing-readme" -- README.md
python scripts/governance/detect_state_drift.py
# Result: NO DRIFT DETECTED (branch mismatch expected on work branch)
git stash pop
```

- `governance` command: `python scripts/governance/detect_state_drift.py`
- `governance_result`: PASS — no state drift in clean context

## Build Results

| Platform | Result |
|----------|--------|
| TypeScript SDK | tsc --noEmit ✅ |
| NexaraCore (Swift) | Build complete ✅ |
| macOS App (Swift) | Build complete ✅ |
| iOS App (Swift) | Build complete ✅ |

## Merge Content Verified

All key functions confirmed present on main:
- `_parse_instant()` / `_instant_before()` / `_instant_before_or_equal()` — ISO-8601 parsing
- `save_record_if_absent()` — DB-level atomic lease claim
- `_latest_active_lease()` — unified lease lookup
- `compare_and_set_record_field()` — approval CAS
- `_is_approval_blocked()` — rejected/expired approval dispatch gate
- `processed_in_cycle` — lease conflict skip
- stale recovery `max_attempts` enforcement
- `complete_mission()` evidence gate + lease owner verification

## CI Status

- **GitGuardian**: ✅ PASS
- **NEXARA CI (all 6 jobs)**: ❌ CI_PLATFORM_FAILURE — `runner_name=""`, `steps=0`
- CI failure is GitHub Actions infrastructure issue — no runner was ever allocated. Product code is not at fault.

## Conclusion

**MAINLINE_VALIDATED** — PR #8 squash merge verified. All local validation passes.
