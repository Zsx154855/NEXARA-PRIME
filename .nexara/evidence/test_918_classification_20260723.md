# Test #918 Classification

**Date:** 2026-07-23
**Test:** `tests/test_pr21_review_closure.py::test_console_route_is_not_mounted_without_next_export`
**Classification:** **REAL_FAILURE** (pre-existing, test-isolation defect, non-blocking)

## Root Cause

`api.py:218` hardcodes `ui_root = Path(__file__).resolve().parents[2] / "ui"`, pointing to the real project directory rather than the test's temporary directory. The test creates a clean `Settings` with temp paths, but `create_app()` uses the hardcoded `ui_root` which resolves to the real `/Users/agentos/NEXARA-PRIME/ui` — where `out/index.html` exists from a prior Next.js build. This causes `/console` to be mounted when the test expects it not to be.

## Production Impact

**None.** In production, the behavior is correct:
- When `ui/out/index.html` exists → `/console` is mounted ✅
- When `ui/out/index.html` does not exist → `/console` is not mounted ✅

## Fix Recommendation

Make `ui_root` configurable via `Settings`:
```python
# In Settings dataclass, add:
ui_root: Path | None = None

# In api.py create_app(), use:
ui_root = settings.ui_root or (Path(__file__).resolve().parents[2] / "ui")
```

This would allow tests to set `ui_root` to a temp directory with no `out/` subdirectory.

## Verdict

Not a production bug. Test-isolation defect. Tracked for future cleanup. Does not block release.
