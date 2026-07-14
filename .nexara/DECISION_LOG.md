# Decision Log

## 2026-07-15 — Program Fact Baseline Consolidation V1

- **Decision:** Execute NEXARA_PROGRAM_FACT_BASELINE_CONSOLIDATION_V1
- **Context:** `.nexara/` had 5 files pointing to 3 different gate names (AGENTSOS_ENGINE_INTEGRATION_V1, REPOSITORY_BASELINE, PRODUCTION_CONNECTORS_AND_SECURITY_V2). Three core mother files (Constitution, Blueprint, Gates) were on Desktop but not in repo. Need single authoritative fact layer for G0–G10 continuous delivery.
- **Actions:**
  1. Verified baseline: 507/507 tests, HEAD 66a86f8, Python 3.12.13
  2. Copied 3 core mother files from Desktop/DOCX to repo root
  3. Created unified `.nexara/` fact layer: PROGRAM_STATE.json, GATE_STATUS.json, PROJECT_FACTS.json, BASELINE.json, KNOWN_BLOCKERS.json
  4. Mapped 3 legacy gate names to G0–G10 framework
  5. Marked old state files as DEPRECATED (not deleted)
  6. Ran secret scan (0 findings), dependency scan (hermes_runtime_dependency=0)
  7. Generated baseline evidence reports in reports/program/baseline/
  8. Atomic local commit
- **Rationale:** Single Writer, single fact source. All future Claude sessions read Constitution → Gate DAG → GATE_STATUS.json to resume continuous delivery.
- **Signed:** Claude Code Prime

## 2026-07-10T23:16:06Z — Baseline Gate Start [DEPRECATED]

- **Decision:** Execute NEXARA_PRIME_REPOSITORY_BASELINE_AND_STATE_TRACKING_V1
- **Context:** User confirmed 10 legacy notes for permanent deletion; repo needs git baseline, .gitignore, CLI status/doctor commands
- **Rationale:** Establish trusted, auditable repository foundation before proceeding to production connectors
- **Signed:** Hermes Agent / 小马
- **Status:** Superseded by Program Fact Baseline Consolidation V1 (2026-07-15). Legacy gate name mapped as pre-G0 milestone.
