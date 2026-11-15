# NEXARA independent QA Sidecar — isolated MVP

Status: **SOURCE CANDIDATE / NOT AN INDEPENDENT QA RUNNER**.

This is an offline, dependency-free validator for evidence produced by NEXARA PR #76. It checks evidence consistency but **deliberately never emits QA_VERIFIED**. It does not generate keys, use an AI model, launch a workflow or deploy a service.

## Repository and Runner findings (2026-11-16)

- Existing `.github/workflows/ci.yml` uses `[self-hosted, macOS, ARM64]` and already runs Python, Ruff, SDK, TypeScript and Swift checks. Preserve it.
- Existing `.github/actions/setup-nexara-python/action.yml` already creates a per-job Python virtual environment. Reuse it rather than introducing a new installer.
- Existing `.github/workflows/sovereign-delivery.yml` only prints a fixed message, so it cannot prove tests or identity.
- The Mac Runner online status, independent account custody and actual runtime isolation are **UNKNOWN**, not established by a workflow YAML file.
- The `sandbox/qa-sidecar-mvp-20261116` branch deliberately avoids the existing `push: work/*` CI trigger; no Runner, secret, CI bill or PR deployment is authorized by this candidate.

## Minimal CLI

Use the sidecar script from this isolated branch against a **clean checkout of the exact PR #76 SHA** and the actual existing Mac evidence directory. The code is intended to be run by an authorized independent QA executor, not accepted merely because a developer ran it.

~~~sh
python3 scripts/qa_sidecar/verify.py \
  --repo /Users/agentos/Worktrees/NEXARA-PR76-ONESHOT-QA-20261115 \
  --evidence /Users/agentos/Documents/NEXARA-PR76-QA-xYmq0y \
  --sha 264addfc277cca937633ca783a3347ed29960470 \
  --statement-out /tmp/nexara-qa-pr76-statement.json
~~~

The command validates checkout HEAD and clean status; sidecar HEAD/exit codes; focused and full test logs; SHA-256 matches; and minimum observed counts. It emits deterministic JSON for an independent signer to inspect. An exit code of **2** with `technical=PASS`, `gate=QA_BLOCKED` is **expected**: it means evidence consistency passed, NOT independent QA. Exit code **3** means evidence validation itself failed. A true external sign-off is not yet available.

To verify a detached OpenSSH signature of the exact calculated statement, supply all of `--signature`, `--trusted-signers`, `--trusted-signers-sha256`, and `--principal`. The trust-anchor file must not be stored inside the source checkout or developer evidence directory. The signature must use the namespace `nexara-qa-sidecar-v1`. **Even valid cryptography does not establish independent key custody**: the caller must separately verify control of the signing identity and the reviewer's authorization. This prototype will still return QA_BLOCKED.

No real Approver key, production account, paid provider API or service is accessed.

## Existing open-source tools — reuse rather than rebuild

- OpenSSH `ssh-keygen -Y verify`: minimal, locally available on macOS, suitable for verifying a detached signature over the generated exact bytes; identity custody is outside the script.
- [Sigstore Cosign](https://github.com/sigstore/cosign): candidate for identity-bound signing of future QA artifacts after separately verifying privacy, OIDC and operational constraints.
- [in-toto Attestations](https://github.com/in-toto/attestation): candidate provenance statement format for later interoperability, not required for this MVP.

GitHub Artifact Attestations for private repositories may require GitHub Enterprise Cloud. Do not enable it or GitHub-hosted Runner minutes without checking plan/entitlement and receiving any needed separate authorization.

## Validate the prototype (no paid model, no actual keys)

~~~sh
python3 -m unittest discover -s tests -p test_qa_sidecar_mvp.py -v
~~~

The tests create disposable Git repositories and evidence bundles. They verify passing evidence remains QA_BLOCKED, tampered hashes, wrong Git SHA, contradictory exit code, and symlink injection. The disposable OpenSSH signing test is skipped where `ssh-keygen` is unavailable.

## Definition of done for a later genuinely independent QA Runner

1. The validating code/policy and trust anchor are pinned **outside developer-controlled PR content**, with changes requiring an independent trust controller.
2. QA executes in an isolated read-only checkout, under a separately controlled identity; never on an unisolated agent-controlled Mac service account with developer credentials.
3. Evidence, runner identity, source SHA, QA policy SHA, run ID, observed exit codes and digest are bound by externally verifiable signatures or equivalent protected system attestations.
4. A second party verifies key custody/control; no developer-created second account or role prompt counts as external independence.
5. Only then may a **separate** formal acceptance process change PR #76 from QA_BLOCKED to VERIFIED_PASS. This candidate alone cannot do so.

**Do not** change PR #76 HEAD, its Draft state, PR #75 dependency, ADR-008 or PR #78/P3. The full regression at PR #76 is already complete; focus on consuming existing evidence and filling the identity boundary.
