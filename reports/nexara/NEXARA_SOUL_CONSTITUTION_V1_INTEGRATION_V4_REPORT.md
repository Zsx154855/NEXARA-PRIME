# NEXARA Soul Constitution V1 Clean Integration V4

- BASE_SHA: `f200082f18fcc37e1e16453f01889d1ef2fd4d73`
- ACCEPTANCE_HEAD: `b5a271774bf87065f2193aa79778e00728979717`
- TESTED_HEAD: `b5a271774bf87065f2193aa79778e00728979717`
- ARTIFACT_HEAD: `b5a271774bf87065f2193aa79778e00728979717`
- TREE_SHA: `daa6558c0e4b6d866eb7e65390f81d97585c0529`
- ALLOWLIST_SHA256: `dd702a8d0ca9debce72a68e1f6695e0e4f2e6a7faa1f241069a05ca6213c743d`
- NEW_REGRESSIONS: `0`
- Observed UTC: `2026-07-30T09:58:15Z`

V4 is rebuilt from the independently repaired main baseline. Soul functionality is limited to the ordered source commits and the necessary conflict-resolution/lint hardening required to keep the canonical gate green. The frozen V3 BLOCKED artifacts remain unchanged and are superseded by this V4 manifest.

Local acceptance is green: Soul tests `8 passed`; full suite `1614 passed, 3 subtests passed`; SDK wire truth/G4/security `143 passed`; canonical Ruff, JSON/schema, contract/runtime alignment, NSEC, secret scan, install/import/compile, and changed-file allowlist all PASS. `NEW_REGRESSIONS=0` against the repaired main baseline.

## Changed-file allowlist

- `constitution/NEXARA_SOUL_CONSTITUTION_V1.md`
- `contracts/nexara/NEXARA_SOUL_CONSTITUTION_V1.json`
- `src/nexara_prime/__init__.py`
- `src/nexara_prime/brain/kernel.py`
- `src/nexara_prime/brain/long_term_memory.py`
- `src/nexara_prime/brain/reasoning/kernel.py`
- `src/nexara_prime/soul.py`
- `tests/brain/phase2a/test_knowledge_graph.py`
- `tests/test_soul_kernel.py`

## Scope proof

- constitution and contract: Soul Constitution V1
- runtime integration: SoulKernel export and ChiefBrainKernel Soul binding
- Soul implementation and Soul tests: direct acceptance scope
- long-term-memory/reasoning/Phase2A test edits: only the ordered source commit's necessary canonical lint cleanup; no new feature delivery
