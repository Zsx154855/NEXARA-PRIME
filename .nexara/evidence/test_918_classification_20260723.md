# Test #918 Classification

**Date:** 2026-07-23
**Test:** `tests/test_pr21_review_closure.py::test_console_route_is_not_mounted_without_next_export`
**Classification:** **RESOLVED** (fixed in 45bb1c2)

## Fix Applied

- `config.py`: Added optional `ui_root: Path | None = None` to `Settings`
- `api.py`: Uses `runtime.settings.ui_root` with hardcoded fallback for production
- `test_pr21_review_closure.py`: Test creates temp `ui/` dir without `out/`

## Result

Clean worktree: 918/918 PASS. Test now passes in all environments.
