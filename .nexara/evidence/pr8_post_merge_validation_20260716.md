# PR #8 Post-Merge Validation — 2026-07-16

## Merge Details

| Field | Value |
|-------|-------|
| PR | #8 |
| Squash merge commit | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| Previous PR HEAD | `7407832d0e06d90a6a7a869d4aa4b1224b82b268` |
| Main local HEAD | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| origin/main HEAD | `2f24d2b9c4b35c956a58730a04392d4075a6bc49` |
| Branch | main |

## Working Tree

- **Status**: `PRE_EXISTING_USER_CHANGE` — README.md contains an injected ID frontmatter unrelated to PR #8
- Not committed, not included in PR #8

## Test Results

| Check | Result |
|-------|--------|
| Orchestration tests | 87 passed, 0 failed |
| Full test suite | 682 passed, 0 failed, 3 subtests |
| Ruff | Clean |
| Governance drift | no drift (branch mismatch fixed, README.md pre-existing) |
| Secret scan | CLEAN |
| git diff --check | Clean |

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

| Check | Status |
|-------|--------|
| GitGuardian | ✅ PASS |
| NEXARA CI (all 6 jobs) | ❌ CI_PLATFORM_FAILURE — runner_name="", steps=0 |

## Conclusion

**MAINLINE_VALIDATED** — PR #8 squash merge verified. All local validation passes. CI failure is infrastructure-only (GitHub Actions runner allocation).
