# Test baseline (takeover/phase1)

## How to run
```sh
bash scripts/test_linux.sh          # fast subset (~50 tests)
bash scripts/test_linux.sh --full   # whole suite (~14 min)
bash scripts/test_linux.sh --one tests/test_t1_deterministic_report.py
```
Requires `PYTHONPATH=src:platform/sdk/python` (the script sets it) and the
installable deps: fastapi, pydantic, uvicorn, python-multipart, httpx2, pytest, pyyaml.

## Current state (2026-11-02, Linux aarch64)

| Suite | Result |
|---|---|
| fast subset (T1/T2/T3/T4 + API + evaluation + stage recovery) | **50 passed** |
| core + stage recovery + T1 | 18 passed |
| hardening + tool runtime + security | 218 passed, 4 failed |

## Known failures (environment, not product logic)
- `test_hardening.py::SandboxUnitTests::*` (3): require macOS `sandbox-exec`.
  On Linux the tool reports `os_sandbox_unavailable` and fails closed.
- Any test that asserts a command executes without a backend will fail until
  `NEXARA_SANDBOX_ALLOW_PROCESS_FALLBACK=true` is set *and* the test is marked
  as using the process backend.

## History
- Pre-takeover full run (same commit f4a5400): 2259 passed / 44 failed.
- This baseline is intentionally **not all green**: the goal is a list where
  every failure has a named cause.

## UI checks (2026-11-02)
- `npm ci` → 375 packages, 639 MB.
- `npx tsc --noEmit` → **exit 0**.
- `next build` → **blocked by the runtime**: Next injects `--single-generation`
  into `NODE_OPTIONS` for its build worker, and this Node build rejects that flag
  (`ERR_WORKER_INVALID_EXEC_ARGV`). Not a code defect; the build must run on a
  Node without that restriction (or a newer/older Next).
- `scripts/ui/route_truth.py` → 28 UI endpoints, **0 missing** in `api.py`.
