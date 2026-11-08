# CAB-01 | Trusted Cognitive-to-Execution Admission Bridge

**Product:** independent NEXARA-PRIME (not BLACK FACTORY / UNSEEN)  
**Status:** PARTIAL — actual GitHub code is implemented; Mac/native-repository/live-OpenMausBot acceptance is NOT_VERIFIED.  
**Base:** PR #60 `80d9398a73ba8c17f58fd3ad2c383227e2b06c77` → #59 → #58 → #57 → main, all Draft.

## Audited root causes (confirmed in code)

1. PR #57 `AutonomousGoalLoop.tick()` intentionally emits `execution_authorized=False`: a cognitive insight is not permission.
2. PR #58's original `submit_proposal()` accepted HYPOTHESIS / EVIDENCE_BACKED status as dispatch admission. PR #60 added `WorkContract`+Guard checks, but both could be manually constructed by the caller.
3. `ChiefBrainKernel.submit()` still takes gate booleans directly and hardcodes `authority_verified=True`; it is **not** itself an authenticated authority oracle.
4. `ExecutionProof.submit()` and `reconcile()` could invoke OpenMausBot without any authority verification. The standalone runner's `resume` could have caused a fresh send of a queued mission even though `submit` was blocked.
5. `PolicyService` wraps existing `PolicyEngine` and `ApprovalEngine`; the latter **already** persists approval request origin and decision event records, including subject/identity, scope, expiry, expected cost, and immutable request digest. No second approval database is needed.

## Minimal actual code changes

- New `integrations/cab01_admission.py`: `CAB01TrustedAdmission` reads **actual canonical SQLiteStore record envelopes** (immutable cognitive goal + latest-version work contract); verifies the exact accepted `ApprovalEngine.list/get` request/decision linkage and contract digest, allowed action, project/mission/proposal/contract identity, bot/thread/executor identity, absolute canonical workspace under host root, non-expiry, zero fee with **trusted verified engine allowlist**, and append-only approval revocation/contract revocation events; then additionally checks `KernelExecutionGuard.assert_admitted` with exact contract ID/version. Returns the canonical `WorkContract` from storage; no model-supplied boolean grants permission.
- Existing `models.WorkContract` gains only optional, backwards-readable scope fields (project_id, workspace, actions, backend, worker, engine, cost, expiry). This is **not** a new task or approval model.
- `ExecutionProof.submit()` now fails closed before ledger creation or OpenMausBot subprocess unless a real `CAB01TrustedAdmission` is supplied and authorizes the persisted mission. `reconcile()` rechecks before every live wait/retry; inspecting an already terminal record is read-only. `submit_proposal()` remains subject to the same inner guard, so calling it with a forged WorkContract/Kernel context cannot bypass durable checks.
- Standalone `scripts/proofs/openmausbot_execution_proof.py` now blocks both `submit` and `resume` (exit code 3) and retains local `inspect` for read-only evidence. This is a **migration from earlier AEP-03 instructions**, now corrected in `aep03/mac/AEP03_MASTER_HANDOFF.md`.
- `tests/integrations/test_openmausbot_execution.py` preserves existing AEP-02 transport contract tests with an **explicitly labeled OFFLINE fake authority, only inside the test fixture**; new tests verify raw default deny and standalone recovery deny.
- `tests/integrations/test_cab01_admission.py` exercises the real `SQLiteStore` + `ApprovalEngine` + `KernelExecutionGuard` code path with an inert offline CLI: positive authorized send and report-only completion, restart dedup, rejected forged flags/contexts, unknown costs, workspace retarget, expiry, revoked grants, superseded contract, wrong actor or scope, and other negative cases.

## Verification ladder / actual evidence

- **Real connector-level implementation:** separate GitHub branch; immutable source SHA and all files read through GitHub; commits and PR diff verified.
- **Isolated executable test:** The GitHub `src/nexara_prime/integrations/cab01_admission.py` source was copied **byte-for-byte** to a separate local ChatGPT container and checked with `git hash-object`: **`5c21a296795aecc77b328eece4a78feea9e48bd5`** matched the remote source blob exactly. Python 3.13.5 compiled that source; **21 PASS / 0 FAIL**, `pytest -q`, exit 0, 0.14s. Smoke log SHA-256 **`ac32a86ac518bd40c0a367b0c3d0b243ad6f87d4cc82f6881290cd771d564dfa`**. This test uses stand-in model, store and kernel collaborator implementations: it is an **exact-source, isolated policy-logic test, NOT a full native NEXARA repo test**.
- **Repository-native tests NOT_EXECUTED:** new `test_cab01_admission.py`, legacy AEP-02 suite, brain/Kernal/Policy suites, Ruff, and full regression. The container has no NEXARA checkout (network DNS blocked), and GitHub Actions has no recorded native Mac jobs for this branch. Do **not** claim the new repository tests pass yet.
- **Real OpenMausBot/Agent E2E NOT_VERIFIED:** Mac user's last probe confirmed service v0.1.148 and CLI parameter compatibility, but native repo path and no-additional-cost model were not available/confirmed. No real Agent task was sent this turn; provider spend in this turn = 0.

## Security boundary that remains open (must not be hidden)

- `ApprovalEngine.decide(... actor=...)` accepts a caller-provided actor string; a model process with direct write access to the canonical DB or permission to call the privileged service could forge both model and approval events. **The actual trusted owner session/OS identity boundary is not provided by this Python library**. Do not make the DB or OpenMausBot CLI credentials available to untrusted Worker processes.
- An approved `KernelAdmissionContext` is still an in-process dataclass; it is not an unforgeable token. The bridge validates canonical approvals **in addition** to the existing Guard, not instead of them.
- `CAB01TrustedAdmission` must be constructed by the OS-isolated trusted NEXARA host using a pinned canonical DB and verified zero-cost engine registry. A caller with arbitrary local Python execution can create its own store/authority or call the OpenMausBot binary directly. This code is **not** an OS sandbox or protected remote gateway.
- The existing governance API has no verified owner-authenticated revoke-approval command for already approved grants; CAB recognizes durable `approval.revoked` / `cab.contract.revoked` events, but production revocation emission/identity enforcement is still missing.
- Revoking an in-flight job blocks new calls through this adapter, **not** already-committed external effects nor the running Agent's internal tool calls. Actual OpenMausBot cancellation/permissions must be evaluated separately.
- The current Kernel `submit` boolean API and legacy runtime surfaces need a trust-domain audit before claiming complete production safety. `WorkContract` application policy/OS ACL does not automatically constrain every child tool once a task starts.
- Even a correctly configured engine name is not proof of zero cost: the `verified_zero_cost_engines` allowlist must come from independent provider/billing evidence controlled by the trusted host.

## Follow-on high-value test (CAB-01 Gate A first)

1. Fresh isolated Mac clone of this PR HEAD, Python >=3.12, existing locked dependencies, no original dirty worktree mutations.
2. `python -m pytest tests/integrations/test_cab01_admission.py tests/integrations/test_openmausbot_execution.py tests/brain/test_cognitive_continuity.py tests/test_kernel_enforcement.py tests/test_g3b_policy_service.py tests/test_g6_governance_hardening.py -q --tb=short`; preserve raw exit/log hash, fix any actual failures in a new follow-up commit and run full regression against main.
3. Wire a real trusted host admission producer that creates/scopes the canonical `WorkContract`, obtains *identity-authenticated* preauthorization, persists verified approval and kernel binding. Test expiry, revocation, in-flight cancel and cross-process races with actual OpenMausBot in a no-data isolated account/VM.
4. Only after verified provider zero-cost and host ACL/sandbox, perform AEP-03 three real Agent Task A→QA→Memory→Task B transfer. Independent evaluator controls success; `REPORTED` is never `ACCEPTED`.

## Skills Ledger

| Skill | Source | Status / actual use |
|---|---|---|
| NEXARA sovereign OnePass v2.1 | `.qoder/skills/nexara-sovereign-onepass-program/SKILL.md`, blob `d44832d1ee0055996752aed7bc22deb9d9f23e03` | READ/USED: isolated branch, no duplicate scheduler, explicit no-claim test status, SHA-based evidence |
| validate-data | `skills://plugins/data/validate-data/skill.md` | READ/USED: evidence provenance and difference between exact-source isolated tests vs native regression |
| read-docs | `skills://plugins/app-6a314a73f8ac819195b0d55e36b9c609/read-docs/skill.md` | READ; NOT_APPLICABLE for this direct repository-source diff (no new official API claims) |
| Four user-created ChatGPT personal Skills | current `skills__list` exposed 140 plugin skills, none of those four were callable | SKILL_ACCESS_BLOCKED, not claimed absent |
| Token/Context optimizer | no callable matching skill | BLOCKED skill, equivalent incremental GitHub reads and SHA-frozen summaries USED |

## Five Gate status

A Mac full Git baseline: **BLOCKED**; B real three Agents: **BLOCKED**; C live CLI authorization/identity: **PARTIAL**; D real restart/revocation: **PARTIAL**; E learning transfer: **BLOCKED**. CAB-01 repository code: **CODE_WRITTEN**; native tested: **NOT_VERIFIED**; live integrated: **NOT_VERIFIED**. No main merge, permanent service, production edit, secret access or paid provider calls.
