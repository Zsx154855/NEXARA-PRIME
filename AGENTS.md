# NEXARA-PRIME — Agent Instructions

## What This Is
NEXARA-PRIME is a governed first-party AI runtime — not a one-shot codebase. It owns Mission creation, planning, approval, execution, verification, evidence commit, memory patch, evaluation, and completion, all governed by NSEC V2.0 (19 chapters, 55 articles).

## Tech Stack
- **Backend:** Python 3.9, pytest, SQLite (persistent), FastAPI (REST API)
- **Frontend:** Next.js 16, React 19, TypeScript strict, Tailwind v4, shadcn/ui, Lucide React
- **CI:** GitHub Actions (local sovereign verification as primary; GitHub CI degraded due to billing lock)
- **Governance:** NSEC V2.0 — supreme engineering constitution at governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2.md

## Quick Commands
```bash
python3 -m pytest -q          # Full test suite (~820+ tests)
python3 -m pytest -q tests/test_runtime_v2_codex_regression.py  # PR #18 regression
python3 scripts/governance/validate_nsec.py   # NSEC governance integrity
python3 scripts/governance/detect_nsec_drift.py   # NSEC drift detection
ruff check src tests           # Lint
python3 scripts/security/scan_hardcoded_secrets.py  # Secret scan
git diff --check               # Whitespace check
```

## Project Structure
```
src/nexara_prime/
  runtime.py        # NexaraRuntime — 5 stage processors (execute→verify→evidence→memory→eval)
  models.py         # Mission, MissionState, FailureCode (32), ReasonCode (34)
  model_gateway.py  # ModelGateway, MockProvider, UnavailableProvider
  state_machine.py  # MissionStateMachine — legal transition matrix
  evidence.py       # EvidenceStore — idempotent evidence with envelope integrity
  memory.py         # MemoryKernel — evidence-bound memory patches
  evaluation.py     # EvaluationEngine — idempotent evaluation
  api.py            # FastAPI REST API — inspect_mission + SDK compatibility fields
  cli.py            # CLI — mission create/status/plan/approve/run
  tools.py          # ToolRuntime — goerned tool invocation
  governance.py     # ApprovalEngine, PolicyEngine, WriterLeaseManager
  config.py         # Settings — from_env, model_provider, mock_model
  recovery.py       # DurableRecovery — checkpoint/idempotency
tests/
  test_runtime_v2_codex_regression.py   # PR #18 regression (19 tests)
  test_runtime_v2_stage_recovery.py     # Stage crash recovery (10 tests)
  test_runtime_v2_entry_convergence.py  # API/CLI/UI entry convergence (15 tests)
  test_runtime_v2_provider_unavailable.py  # Provider unavailable (13 tests)
  test_runtime_v2_crash_recovery.py     # Crash recovery (3 tests)
  test_chief_brain_runtime_convergence.py  # Chief brain convergence (27 tests)
reports/           # Evidence/Receipt delivery files
.nexara/evidence/  # Evidence JSON — git-tracked
```

## Code Style
- Python: type annotations (from __future__ import annotations), dataclasses over dicts
- TypeScript: strict mode, no `any`, named exports, PascalCase components, camelCase utils
- Tailwind utility classes, no inline styles
- 2-space indentation, trailing commas

## Runtime Invariants (Must Never Break)
1. **No silent MockProvider fallback** — mock_model=true is only path to MockProvider
2. **No raw store.find_record bypass** — replay from mission.result, not raw store
3. **No self-transitions** — stages advance forward only (Execution→Verification→Evidence→MemoryPatch→Evaluation→Completed)
4. **No state regression** — resume() only unpauses, never resets mission.state
5. **No duplicate side effects** — all stage artifacts keyed with idempotency_key
6. **Approval integrity** — approval_status starts as "integrity_error", not silent "pending"
7. **Evidence integrity** — evidence.verify() called via public EvidenceStore API before relying on stored content
8. **Provider unavailable is resumable** — mission stays in Execution, not terminal Failed
9. **Adaptive states rejected** — Running/Verifying/Degraded → ADAPTIVE_RECOVERY_REQUIRED
10. **SDK compatibility inline** — state, spec, title, objective, created_at in inspect_mission

## Agent Orchestration (When Using Claude Code)
- **Single writer** — one agent modifies runtime/tests at a time
- **Parallel inspection** — multiple agents can read/audit independently
- **Before any commit:** full pytest suite + ruff + NSEC + secret scan
- **Before any push:** await explicit human approval gate (NSEC Article 37)
- **Worktree isolation** — complex tasks use git worktrees, merge after verification

## NSEC Governance Quick Reference
- **Article 1**: Fixed engineering loop — audit→fix→verify→evidence→commit→push (no incremental patching)
- **Article 8**: Maximum reachable endpoint — advance as far as possible in one round
- **Article 9**: No artificial splitting — don't break completable work into multiple rounds
- **Article 26**: Quality must not degrade — no deleting tests, no relaxing gates
- **Article 28**: Reality first — facts over predictions; if fact contradicts expectation, fix the reasoning
- **Article 37**: High-impact approval — push/merge/tag/release/deploy require explicit human approval
- **Article 45**: Definition of done — not "code written" but tests+evidence+receipt+governance all clear
- **Article 55**: Complete delivery responsibility — deliver complete artifacts, not fragments

## Known Active Branches
- `main` — merge target for all PRs (b37d0f31)
- `work/nexara-chief-brain-real-mission-product-closure-v1` — Claude Code closure V1 (bcf0434, unpushed)
- `work/nexara-chief-brain-runtime-convergence-v2-clean` — PR #18 merged (105b536)

## Most Important Notes
- Never `curl | python3` — blocked by NSEC security rules
- Never `git add .` — always use explicit file staging
- Never push without explicit human approval gate
- Every Evidence/Receipt must be git-tracked with verifiable SHA-256
- Test suite baseline: 839 tests (origin/main: 742, v2 additions: 97)
- ruff F401 clean on new code (pre-existing AdaptiveMode unused import tolerated)
