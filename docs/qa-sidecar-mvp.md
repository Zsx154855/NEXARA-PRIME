# NEXARA QA Sidecar v0.2 — current engineering status

**SOURCE CANDIDATE ONLY — Mac integration and independent QA identity NOT VERIFIED.** This addendum supersedes the v0.1 CLI contract below.

## v0.2 trust and evidence requirements

- Developer-controlled CLI can no longer supply --sha, --repo-id, --min-full, --min-focused, --principal or --trusted-signers-sha256. Versioned JSON policy is required as external input, protected by the *independent* QA controller; its SHA-256 must be pinned out-of-band. A developer-supplied policy + pin is smoke-test-only, not an authority.
- Validate clean Git SHA, expected origin configuration, single-valued HEAD/exit fields, exact expected log digest against both policy and checksum file, manifest path binding, exact test counts and symlink/path substitution.
- Local 'git remote origin' is unauthenticated configuration, not actual upstream proof. The independently authenticated QA reviewer must separately verify the PR SHA.
- Detached OpenSSH signature validation is optional and uses the signer's identity and allowed-signers SHA in the policy. Even a valid signature still yields QA_BLOCKED until independent credential custody is proven.

## One-shot Mac smoke (not executed by this ChatGPT session)

```bash
bash scripts/qa_sidecar/mac_one_shot.sh
```

The script runs the Sidecar fixture tests (disposable OpenSSH signing test if ssh-keygen is available), then checks existing PR #76 logs only, creating a fresh ~/Documents/NEXARA-QA-SIDECAR-MAC-* evidence directory. It does not run the 2445-test PR #76 regression, trigger CI, use paid models, deploy services or generate production secrets.

Expected success indication: MAC_SMOKE=TECHNICAL_PASS_IDENTITY_BLOCKED; this is **not** formal independent QA acceptance.

docs/qa-sidecar-pr76.example-policy.json is developer-controlled and is DEMO ONLY, **not** a trusted acceptance policy.

## v0.2 verifier CLI

```bash
python3 scripts/qa_sidecar/verify.py \
  --repo /Users/agentos/Worktrees/NEXARA-PR76-ONESHOT-QA-20261115 \
  --evidence /Users/agentos/Documents/NEXARA-PR76-QA-xYmq0y \
  --policy /independent/controller/policy.json \
  --policy-sha256 PIN_APPROVED_OUT_OF_BAND
```

Optional signature verification uses --signature SIGNATURE_PATH and --trusted-signers ALLOWED_SIGNERS_PATH. Exit 2 with JSON technical=PASS/gate=QA_BLOCKED means evidence was consistent without identity proof; exit 3 means blocked evidence. Argparse invalid arguments may also return 2 but do not produce valid JSON; parse result JSON, not the exit code alone.

**Frozen boundary:** PR #76 remains Draft, its technical test results are retained, QA_BLOCKED remains until separate verified identity. This design candidate does not modify PR #76, PR #78, ADR-008 or production.

---

# Superseded v0.1 notes (historic; CLI below no longer applies)
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
