# G0 Reality Inventory V2 — 2026-07-23

**基线:** main HEAD dd0505ac53721d8e2e6150e47936119fe16734d6
**蓝图:** NEXARA_PRIME_SOVEREIGN_AGENT_MASTER_BLUEPRINT_V1.md (frozen)
**宪法:** NEXARA_PROGRAM_CONSTITUTION_V1.md + NSEC V2.1
**执行模式:** 只读盘点 — 禁止 Push/Merge/Deploy/重建已有权威能力

---

## 1. Repository Inventory

### 1.1 仓库身份

| Field | Value |
|-------|-------|
| Path | `/Users/agentos/NEXARA-PRIME` |
| Remote | `https://github.com/Zsx154855/NEXARA-PRIME.git` |
| Branch | `main` |
| HEAD | `dd0505ac53721d8e2e6150e47936119fe16734d6` |
| Python | 3.12.13 (`.venv`) |
| Package | nexara-prime==0.1.0 |

### 1.2 顶层目录结构

```
NEXARA-PRIME/
├── .claude/           # Claude Code agents/commands/skills (3 dirs)
├── .claudian/         # Session logs
├── .github/           # CI workflows + setup action
├── .nexara/           # Program state, evidence, receipts, onepass
├── .obsidian/         # Knowledge fabric plugins + themes
├── Chat/              # Excluded from VCS
├── config/            # Product reality constitution
├── dist/              # Build artifacts (DMG, whl, tar.gz, SBOM)
├── docs/              # 14-category knowledge fabric
├── experience/        # Swift clients (macOS + iOS + NexaraCore)
├── extensions/        # Empty plugin dir
├── governance/        # NSEC, baselines, contracts, recovery, releases
├── platform/          # SDK scaffolds (Python/TS/Swift/MCP/REST)
├── reports/           # 24+ acceptance/audit/program reports
├── runtime/           # 3 SQLite databases
├── schemas/           # 4 JSON schemas + gate/program schemas in scripts
├── scripts/           # CI, governance, recovery, runtime_truth, security
├── skills/            # Portable skill definitions
├── src/nexara_prime/  # Core package: 65+ .py files, 4 subpackages
├── tests/             # 27 test files, 13,076 lines
├── ui/                # Next.js 16 web dashboard
└── workspace/         # Sample project
```

### 1.3 核心 Python 包 (`src/nexara_prime/`) — 65 files, ~20,000 LOC

**顶级模块 (34):**
`__init__`, `adaptive_runtime`, `adaptive_scheduler`, `api`, `benchmark_runner`, `browser_adapter`, `capabilities`, `capability_registry_v2`(deprecated alias), `cli`, `computer_use_adapter`, `config`, `contract_engine`, `db`, `deployment_adapter`, `escalation`, `evaluation`, `events`, `evidence`, `git_adapter`, `governance`, `identity`, `independent_review`, `memory`, `message_adapter`, `mission_compiler`, `mission_triage`, `model_gateway`, `model_router`, `models`, `network_policy`, `orchestration`, `program_loop`, `rag_pipeline`, `real_context`, `recovery`, `repair_loop`, `resource_budget`, `runtime`, `sandbox_v2`, `scheduler`, `security_audit`, `state_machine`, `token_compiler`, `token_compiler_v2`, `tools`

**Subpackages:**
- `connectors/` (10): audit, base, browser_readonly, health, http_readonly, lifecycle, permissions, provider_connector, registry
- `product_reality/` (4): evolution, genome, models, twin
- `secrets/` (4): base, env, keychain, memory
- `agent/` (1): `__init__.py` only (skeleton)
- `aos/` (0 source .py): **ONLY `__pycache__/*.pyc` — 13 modules, source files MISSING**
- `delivery_controller/` (2): `__init__`, migration
- `platform/` (1): `__init__.py` only (skeleton)

### 1.4 Tests — 27 files, 13,076 lines

| File | Lines | Focus |
|------|-------|-------|
| test_product_reality_v2_full_audit.py | 2153 | Product reality audit |
| test_adaptive_runtime.py | 1535 | Adaptive runtime |
| test_orchestration.py | 1026 | Orchestration control plane |
| test_security_hardening.py | 751 | Security hardening |
| test_nsec_governance.py | 625 | NSEC governance |
| test_chief_brain_closure_v1.py | 624 | Chief brain closure |
| test_hardening.py | 541 | Hardening acceptance |
| test_e2e_runtime_closure.py | 535 | E2E runtime |
| test_python_ci_contract.py | 500 | CI contract |
| test_product_reality_v2_review_fixes.py | 499 | Product reality fixes |
| +17 more files | ~5,200 | Extensive coverage |

Test baseline: 682 passed, 0 failed (current `main` HEAD)

### 1.5 UI (Next.js 16 Web Dashboard)

```
ui/src/
├── app/
│   ├── globals.css
│   ├── layout.tsx          # Root layout with Sidebar + TopBar
│   └── page.tsx            # DashboardShell wrapper
├── components/
│   ├── DashboardShell.tsx   # Main layout orchestrator
│   ├── Sidebar.tsx          # Navigation sidebar
│   ├── TopBar.tsx           # Top bar
│   └── screens/
│       ├── Overview.tsx          # Mission stats + runtime health
│       ├── MissionCreator.tsx    # New mission composer
│       ├── MissionWorkspace.tsx  # Active mission workspace
│       ├── ApprovalCenter.tsx    # Human approval queue
│       ├── CapabilityRegistry.tsx # Capability management
│       ├── EvidenceViewer.tsx    # Evidence chain viewer
│       ├── AgentTeam.tsx         # Agent team status
│       └── RuntimeHealth.tsx     # Runtime health dashboard
├── hooks/                  # Empty (no custom hooks)
├── lib/
│   ├── api.ts             # API client
│   └── utils.ts           # Utilities
└── types/
    └── index.ts           # TypeScript type definitions
```

### 1.6 Swift/Native Clients

```
experience/
├── NexaraApp/             # Xcode project shell (Info.plist only)
├── NexaraCore/            # Shared Swift package
│   └── Sources/NexaraCore/
│       ├── RuntimeClient.swift   # API client
│       └── RuntimeTruth.swift    # Truth verification
├── macos/                 # macOS SwiftUI app
│   └── Sources/NexaraMac/
│       ├── NexaraMacApp.swift, ContentView.swift
│       ├── RuntimeViewModel.swift
│       ├── ComposerDetail, OverviewDetail
│       ├── WorkspaceDetail, EvidenceDetail
└── ios/                   # iOS SwiftUI app
    └── Sources/NexaraIOS/
        ├── NexaraIOSApp.swift, iPhoneTabs.swift
        ├── AdaptiveContentView.swift
        └── IOSRuntimeViewModel.swift
```

### 1.7 Platform SDK (Scaffolds Only)

```
platform/sdk/
├── python/    # nexara_sdk package with client.py + models.py (basic)
├── typescript/# Empty (only node_modules/typescript)
├── swift/     # Empty scaffold
├── mcp/       # server.py exists (MCP server)
└── rest/      # openapi.yaml exists
```

### 1.8 Governance Artifacts

```
governance/
├── NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md    # NSEC V1
├── NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md  # NSEC V2.1 (authoritative)
├── nsec.yaml                                           # NSEC config
├── authority_index.yaml                                # Authority index
├── baselines/v0.1.0/     # 6 baseline files (manifest, checksums, etc.)
├── contracts/            # MERGE_CONTRACT_V1.yaml
├── recovery/             # ROLLBACK_POLICY_V1.md
└── releases/             # RELEASE_FLOW_V1.md + APPROVAL_MATRIX_V1.yaml
```

### 1.9 Documentation (54 .md files in docs/)

14 categories: 01-Product, 02-Architecture (12-Layers), 03-Runtime, 04-Governance, 05-UI-UX, 06-ADRs (7 ADRs), 07-Missions, 08-Failure-Cases, 09-Evidence-Index, 10-Data-Contracts, 11-Evaluations, 12-Operations, 13-Product-Reality, 99-Legacy
