# NEXARA Soul Constitution V1 Clean Integration V4

- BASE_SHA: `f200082f18fcc37e1e16453f01889d1ef2fd4d73`
- ACCEPTANCE_HEAD: `af2f4e3e52e3b9851ab60d3735c9fceda7006bbe`
- TESTED_HEAD: `af2f4e3e52e3b9851ab60d3735c9fceda7006bbe`
- ARTIFACT_HEAD: `af2f4e3e52e3b9851ab60d3735c9fceda7006bbe`
- TREE_SHA: `00a29c820d8c2264006ac236b9b078211e309350`
- ALLOWLIST_SHA256: `b5f4c26196bd071301f965446746a9f97452ef2210da6ef4bc93b064f2ddb99e`
- NEW_REGRESSIONS: `0`
- Observed UTC: `2026-07-30T10:03:27Z`

V4 is rebuilt from the independently repaired main baseline. Soul functionality is limited to the ordered source commits and the necessary conflict-resolution/lint hardening required to keep the canonical gate green. The frozen V3 BLOCKED artifacts remain unchanged and are superseded by this V4 manifest.

Local acceptance is green: Soul tests `8 passed`; full suite `1614 passed, 3 subtests passed`; SDK wire truth/G4/security `143 passed`; canonical Ruff, JSON/schema, contract/runtime alignment, NSEC, secret scan, install/import/compile, and changed-file allowlist all PASS. `NEW_REGRESSIONS=0` against the repaired main baseline.

## Changed-file allowlist

- `constitution/NEXARA_SOUL_CONSTITUTION_V1.md`
- `contracts/nexara/NEXARA_SOUL_CONSTITUTION_V1.json`
- `evidence/nexara/NEXARA_SOUL_CONSTITUTION_V1_INTEGRATION_EVIDENCE_V4.json`
- `evidence/nexara/NEXARA_SOUL_CONSTITUTION_V1_INTEGRATION_RECEIPT_V4.json`
- `evidence/nexara/NEXARA_SOUL_CONSTITUTION_V1_INTEGRATION_V4_SUPERSESSION_MANIFEST.json`
- `reports/nexara/NEXARA_SOUL_CONSTITUTION_V1_INTEGRATION_V4_REPORT.md`
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
