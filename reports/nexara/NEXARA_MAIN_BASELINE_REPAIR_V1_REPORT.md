# NEXARA Main Baseline Repair V1

- BASE_SHA: `52de47c14a7e08f290f47ba2e997aba982431b60`
- TESTED_HEAD: `8e3394a46efa8369684baf2fceed9481aef79542`
- TREE_SHA: `c7b6ff6d51cdeb7627fc062265a7f1772e205ab1`
- ALLOWLIST_SHA256: `8081a7e51a3bbb7efaed97948e51d1965a724f6176a24dbc034e756cd82cee7e`
- NEW_REGRESSIONS: `0`
- Observed UTC: `2026-07-30T09:46:26Z`

The clean `origin/main` baseline had 25 collection errors, 26 canonical Ruff errors, 2 MemoryKind wire-truth failures, and 2 G4 model import failures. The independent repair branch fixes those baseline defects without Soul functionality changes.

Current baseline result: `1606 passed, 3 subtests passed`; collection: `1606 tests collected`; repair targets: `67 passed`; security/SDK/KMA/G4 combined gate: `185 passed`; canonical Ruff, JSON shape, NSEC, secret scan, compile/import all PASS.

## Changed-file allowlist

Every changed file is limited to baseline contracts/runtime repair, historical Phase 3 lint cleanup, or the two missing baseline contract modules:

- `platform/sdk/python/nexara_sdk/models.py`
- `src/nexara_prime/brain/memory_controller.py`
- `src/nexara_prime/brain/mission_intelligence.py`
- `src/nexara_prime/brain/self_reflection_engine.py`
- `src/nexara_prime/models.py`
- `src/nexara_prime/sandbox_v2.py`
- `src/nexara_prime/tools.py`
- `tests/brain/phase3/test_deep_reasoning.py`
- `tests/brain/phase3/test_meta_cognition.py`
- `tests/brain/phase3/test_research_intelligence.py`
- `tests/brain/phase3/test_strategic_planning.py`
- `tests/brain/phase3/test_world_model.py`
