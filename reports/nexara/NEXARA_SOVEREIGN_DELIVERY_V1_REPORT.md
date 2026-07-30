# NEXARA Sovereign Delivery Transition V1

- PARENT_HEAD / BASE_SHA: `52de47c14a7e08f290f47ba2e997aba982431b60`
- ACCEPTANCE_HEAD: `c6cf5015418b8f309d11fb7d51c32861aadfddea`
- TESTED_HEAD: `c6cf5015418b8f309d11fb7d51c32861aadfddea`
- ARTIFACT_HEAD: `c6cf5015418b8f309d11fb7d51c32861aadfddea`
- TREE_HASH: `7f22eb1a195f54c8ab44cddecd208ee619e507ed`
- ALLOWLIST_HASH: `aae51811a2274b6c6cfdafefd44cf66901883f1f4721f2fcc33af48427c8f492`
- NEW_REGRESSIONS: `0`
- GENERATED_AT_UTC: `2026-07-30T11:11:53Z`

NEXARA owns the validation authority in this delivery candidate. The GitHub adapter is transport and review metadata only; no external CI result is used to manufacture local PASS. The branch contains the baseline repairs for the previously observed 25 collection errors, 26 canonical Ruff errors, 2 MemoryKind wire-truth failures, and 2 G4 model import failures, followed by Soul Constitution/Kernel and V4 hardening/lint integration.

Local gates: Soul `8 passed`; full suite `1614 passed, 3 subtests passed`; SDK wire-truth/G4/security `143 passed`; canonical Ruff, JSON/schema, contract/runtime alignment, NSEC, secret scan, import/compile, and allowlist all PASS. `NEW_REGRESSIONS=0`.

## Complete changed-file allowlist

- `constitution/NEXARA_SOUL_CONSTITUTION_V1.md`
- `contracts/nexara/NEXARA_SOUL_CONSTITUTION_V1.json`
- `evidence/nexara/NEXARA_MAIN_BASELINE_REPAIR_EVIDENCE_V1.json`
- `evidence/nexara/NEXARA_MAIN_BASELINE_REPAIR_RECEIPT_V1.json`
- `evidence/nexara/NEXARA_SOUL_CONSTITUTION_V1_IMPLEMENTATION_EVIDENCE_V3.json`
- `evidence/nexara/NEXARA_SOUL_CONSTITUTION_V1_IMPLEMENTATION_RECEIPT_V3.json`
- `evidence/nexara/NEXARA_SOVEREIGN_DELIVERY_PROOF_V1.json`
- `evidence/nexara/commit_chain_proof.json`
- `evidence/nexara/delivery_freeze_v1.json`
- `platform/sdk/python/nexara_sdk/models.py`
- `reports/nexara/NEXARA_MAIN_BASELINE_REPAIR_V1_REPORT.md`
- `reports/nexara/NEXARA_SOVEREIGN_DELIVERY_V1_REPORT.md`
- `src/nexara_prime/__init__.py`
- `src/nexara_prime/brain/kernel.py`
- `src/nexara_prime/brain/long_term_memory.py`
- `src/nexara_prime/brain/memory_controller.py`
- `src/nexara_prime/brain/mission_intelligence.py`
- `src/nexara_prime/brain/reasoning/kernel.py`
- `src/nexara_prime/brain/self_reflection_engine.py`
- `src/nexara_prime/models.py`
- `src/nexara_prime/sandbox_v2.py`
- `src/nexara_prime/soul.py`
- `src/nexara_prime/tools.py`
- `tests/brain/phase2a/test_knowledge_graph.py`
- `tests/brain/phase3/test_deep_reasoning.py`
- `tests/brain/phase3/test_meta_cognition.py`
- `tests/brain/phase3/test_research_intelligence.py`
- `tests/brain/phase3/test_strategic_planning.py`
- `tests/brain/phase3/test_world_model.py`
- `tests/test_soul_kernel.py`

## Scope proof

- baseline repair files address the frozen collection, Ruff, MemoryKind, and G4 defects;
- Soul files implement the Constitution V1 and runtime kernel acceptance surface;
- evidence, receipt, freeze, proof, and report files are this delivery's auditable control plane;
- no Provider Runtime, external Tool Runtime delivery, unrelated Evidence history, or deployment artifact is introduced.
