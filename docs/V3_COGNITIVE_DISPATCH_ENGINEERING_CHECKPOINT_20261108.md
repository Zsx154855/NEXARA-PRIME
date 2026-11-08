# NEXARA-PRIME V3.0 | Cognitive Dispatch Admission Engineering Checkpoint

**Date:** 2026-11-08. **Scope:** independent NEXARA-PRIME. **Status:** CODE_WRITTEN / REPOSITORY_TEST_NOT_VERIFIED / LIVE_AGENT_BLOCKED.

## Root cause and minimal fix

PR #57 `AutonomousGoalLoop.tick` returns cognitive proposals that explicitly have `execution_authorized=False`. PR #58 `ExecutionProof.submit_proposal()` previously forwarded a `HYPOTHESIS` or `EVIDENCE_BACKED` JSON directly into the OpenMausBot CLI. The proposal status is epistemic, not execution permission. Without real Kernel admission, a model or untrusted caller could try to convert its own text into an executable Agent instruction.

**Patch on isolated branch**:

- Existing `WorkContract` (model) and `KernelExecutionGuard` (runtime boundary) are reused. `submit_proposal` now requires both, verifies approved contract and `approved_at`, binds contract's `provenance` to the cognitive `proposal_id`, checks an active admitted `mission_id`, and binds admitted `metadata.contract_id` to the exact approved contract ID. The actual OpenMausBot mission ID is the real approved `contract.mission_id`, never a self-generated cognitive proposal ID.
- Standalone `openmausbot_execution_proof.py submit` based solely on JSON now returns `BLOCKED / trusted_kernel_admission_required` (exit 3) without creating a lab ledger; only `inspect`/`resume` remain available from the standalone runner. Real dispatch must come from a trusted in-process NEXARA Controller that has performed **actual** mission approval/evidence checks.
- Original integration test has been adapted to use admitted WorkContract + Guard; additional negative tests cover spoofed `execution_authorized=True`, draft contract, wrong source goal, wrong mission, wrong contract ID, incomplete admission, malformed proposal and blocked standalone CLI.
- The AEP-03 handoff was corrected to no longer instruct Mac Agents to run the JSON-only submit command.
- Mac `aep03_local_gate.py probe` now requires Python >=3.12 before returning READY; Apple's Python 3.9.6 was previously insufficient for `pyproject.toml`.
- V3 product goals and measurable acceptance criteria are captured in `docs/NEXARA_ADAPTIVE_COGNITIVE_OS_V3_ENGINEERING_BASELINE_20261108.md`; no new scheduler, learning database or global governance engine was added.

**Boundary limitation:** `KernelAdmissionContext` is an in-process dataclass and existing `ChiefBrainKernel.submit` takes gate booleans from its trusted caller. The new adapter check **does not prove** those booleans were calculated independently, cryptographically authenticate an external user, force model-free API billing or create an OS sandbox. Direct low-level `ExecutionProof.submit()` remains available for explicitly trusted lab Controllers; its callers must be constrained at the real tool boundary. Production acceptance needs a real wired Controller, provenance-authenticated records, provider billing enforcement, workspace isolation and independent test receipts. Treat any claim of 'complete OS security' here as false.

## Verification and evidence

1. GitHub tool operations: read PR #53/#54/#55/#57/#58/#59, inspect actual class definitions in `models.py`, `kernel_boundary.py`, `brain/kernel.py`, `contract_engine.py`, `cognitive_continuity.py`, `integrations/openmausbot_execution.py`; create isolated branch and commit modified source/tests/docs via GitHub Contents API.
2. Local Python 3.13.5 mirrored admission-logic test (in separate ChatGPT container): **7 passed / 0 failed**, `pytest -q`, exit 0. Log SHA-256: `775b7aa27d0c17f48b3feff20c836f14b6ed8ebcb90ec7e0b76d2a13c579268a`. **MIRROR**, not actual checkout, not repo-native pytest.
3. Repo-native `tests/integrations/test_openmausbot_execution.py`, `tests/brain/test_cognitive_continuity.py`, Ruff, full regression, Mac CI, OpenMausBot server, real Researcher/Engineer/QA, cost and A→B transfer: **NOT_EXECUTED / NOT_VERIFIED** in this ChatGPT environment. GitHub Actions require self-hosted Mac ARM64 runner.
4. User's most recent Mac probe report: OpenMausBot Server 0.1.148 reachable; 5 configured engines do **not** establish zero marginal cost; old local Git worktrees broken and CI clone incomplete. Re-clone full GitHub graph in a clean worktree, run Python >=3.12, and independently check billing and isolated account/VM before any external Agent execution.
5. Main was not merged; original six PRs' Draft branches remain independent or stacked as before. No production config, secrets or permanent background service affected. **New paid provider calls: 0 in this conversation.**

## Skills Usage Ledger (actually used, not guessed)

| Skill | Source | Actual state | Evidence / use |
|---|---|---|---|
| NEXARA sovereign onepass program v2.1 | `.qoder/skills/nexara-sovereign-onepass-program/SKILL.md` (GitHub verified source) | READ / USED | Read complete file, followed existing NSEC authority, single-writer, separate Draft work, no mock-as-real, no duplicate schedulers; GitHub tools operated on frozen refs. It is **not** claimed as a Qoder runtime invocation. |
| validate-data | `skills://plugins/data/validate-data/skill.md` | READ / USED | Veracity check: separated Mac Git evidence, local mirror, repo-native tests and true Agent E2E. |
| design-kpis | `skills://plugins/data/design-kpis/skill.md` | READ / USED | Defined denominators/guardrails for accepted results, transfer, resource efficiency and verified capability growth. No invented baseline target. |
| read-docs | `skills://plugins/app-6a314a73f8ac819195b0d55e36b9c609/read-docs/skill.md` | READ, NOT_APPLICABLE | Loaded for official API behavior; current task depended on actual GitHub code and user-confirmed CLI so no new external doc-fetch was needed. |
| 持续自主研发总控 / 受控执行器与故障恢复 / 智能体能力评测 / HTML 图解回答 | owner personal ChatGPT Skills | SKILL_ACCESS_BLOCKED | Current `skills__list` enumerated 140 installed plugin skills; these personal skills were not exposed as callable URIs. Not claimed absent or active. |
| Token/context optimization | no callable matching skill discovered | BLOCKED (skill only), equivalent procedures USED | Pinned SHAs, relevant file ranges, batched independent GitHub reads, concise checkpoint, no broad log injection and no paid delegation. |

## Next real mission: read-only/native Gate A then real AEP-03

On Mac, use the current stacked PR branch after rechecking HEAD:

```bash
git clone --no-single-branch --branch work/v3-cognitive-execution-admission-20261108 \
  https://github.com/Zsx154855/NEXARA-PRIME.git /NEW_DISPOSABLE_PATH/NEXARA-V3
cd /NEW_DISPOSABLE_PATH/NEXARA-V3
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]' pytest
.venv/bin/python -m pytest tests/brain/test_cognitive_continuity.py tests/integrations/test_openmausbot_execution.py -q --tb=short
```

- Use an available Python >=3.12 already installed; do not upgrade system Python or install new paid dependencies without review. Replace the placeholder path with a fresh disposable directory, not the user's original tree. Run existing security/lint/full regression and compare against main as available.
- Before real dispatch, wire a trusted Controller with actual admission evidence, `KernelExecutionGuard`, `WorkContract`, OS workspace isolation, a **proved** zero-incremental-cost model and dedicated OpenMausBot thread. Do not add a second Policy/Memory scheduler.
- Then perform actual three-Agent Task A patch, independent QA, adapter recovery and Task B memory transfer vs control, preserving real tool/time/hash/identity receipts. Retain `REPORTED` separate from `ACCEPTED`.

## Gate truth (this checkpoint)

| Gate | Status |
|---|---|
| A — Mac native and fixed-SHA repo regressions | BLOCKED |
| B — real OpenMausBot 3-Agent result | BLOCKED |
| C — contract identity and task result binding | PARTIAL (code written, repo-native tests not run) |
| D — actual disconnect/recovery | PARTIAL (prior fake CLI tests only) |
| E — independently accepted, transferred experience | BLOCKED |

**Not merge-ready.** The next user action is NOT 'continue' planning; the missing resource is a real authorized Mac test/Agent execution channel with a clean Git repository and proven no-additional-cost model.
