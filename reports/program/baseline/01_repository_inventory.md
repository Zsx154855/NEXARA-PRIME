# 01 — Repository Inventory

**Date:** 2026-07-15
**Baseline:** NEXARA_PROGRAM_FACT_BASELINE_CONSOLIDATION_V1

## Repository Identity

| Field | Value |
|-------|-------|
| Path | `/Users/agentos/NEXARA-PRIME` |
| Remote | `https://github.com/Zsx154855/NEXARA-PRIME.git` |
| Branch | `work/nexara-adaptive-runtime-v1` |
| HEAD | `66a86f8a0d1712d75b2af78cb1ad8b08783af7bb` |

## Top-Level Directory Structure

```
NEXARA-PRIME/
├── .claude/            # Claude Code configuration
├── .claudian/          # Claude Code agent definitions
├── .nexara/            # Program state & gate tracking
├── Chats/              # Excluded from version control
├── config/             # Product reality constitution
├── dist/               # Build artifacts
├── docs/               # Knowledge fabric (14 categories)
├── extensions/         # Plugin architecture
├── platform/           # Platform P1 manifests
├── reports/            # Acceptance & evidence reports
├── runtime/            # SQLite DB & runtime data
├── schemas/            # JSON/YAML data contracts
├── scripts/            # Operational scripts
├── skills/             # Portable skill definitions
├── src/nexara_prime/   # Core Python package (50 modules)
├── tests/              # Test suite (507 tests)
├── ui/                 # Frontend assets
└── workspace/          # Sample projects
```

## Core Python Package (`src/nexara_prime/`)

50 Python modules across 4 subpackages:

- **Top-level (34):** `__init__`, `adaptive_runtime`, `adaptive_scheduler`, `api`, `capabilities`, `capability_registry_v2`, `cli`, `config`, `contract_engine`, `db`, `escalation`, `evaluation`, `events`, `evidence`, `governance`, `identity`, `memory`, `mission_compiler`, `mission_triage`, `model_gateway`, `model_router`, `models`, `network_policy`, `recovery`, `resource_budget`, `runtime`, `sandbox_v2`, `scheduler`, `security_audit`, `state_machine`, `token_compiler`, `token_compiler_v2`, `tools`
- **connectors/ (8):** `__init__`, `audit`, `base`, `browser_readonly`, `health`, `http_readonly`, `lifecycle`, `permissions`, `provider_connector`, `registry`
- **product_reality/ (4):** `__init__`, `evolution`, `genome`, `models`, `twin`
- **secrets/ (4):** `__init__`, `base`, `env`, `keychain`, `memory`

## Pip Package

- **Name:** nexara-prime==0.1.0
- **Entry Point:** `nexara` → `nexara_prime.cli:main`
- **Python:** >=3.12
