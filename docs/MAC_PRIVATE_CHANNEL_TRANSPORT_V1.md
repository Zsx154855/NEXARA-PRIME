# NEXARA Mac Relay — Private GitHub channel, transport gate v1

**Status:** SOURCE-ONLY / NOT DEPLOYED / NOT CONNECTED TO USER MAC.  
**Project:** independent NEXARA-PRIME intelligent-agent brain, not BLACK FACTORY / UNSEEN.  
**Authorization reference:** Issue #63 (scope record, never execution authority).  
**Prohibited public mailbox:** Issue #56 remains read-only, with no private task payloads.

## Why this change is narrow

The real P1/P2/P3 `nexara_mac_relay_v01` implementation and its local
`codex/nexara-durable-mac-relay` branch currently exist only on the user's
Mac; some files are staged/modified. This branch MUST NOT reconstruct or
overwrite those unpublished files. Existing P3 signing/approval logic, the
one-owner SQLite lease/epoch, dedicated Broker and CAB-01 are authoritative.
The new `integrations/private_channel_transport_v1.py` inspects a minimal
private GitHub **reference** and returns **no execution authority**.

## One-way outbound data flow

1. The ChatGPT GitHub connector sends a task **reference only** to a verified
   private task repository (or another separately approved private channel).
   Creating that repository and assigning a dedicated credential must follow
   Issue #63 and trusted local UI; no high-privilege `gh` token reuse.
2. A dedicated non-admin Mac Broker polls outbound HTTPS. It verifies the
   repository ID, owner numeric ID, issue number, private status, API author,
   immutable comment ID, and strict time-bounded reference using this module.
   All metadata MUST be read from authenticated GitHub responses by the Broker;
   never from a model-supplied JSON wrapper.
3. **Independent mandatory gates, before every dispatch AND resume:**
   - The Broker's existing P3 cryptographic signature verifier validates the
     true canonical request and its signing identity (the `signed_sha256`
     field here is ONLY a reference, NOT proof of a signature).
   - Existing P3 SQLite owner/lease/epoch/replay protection atomically consumes
     a unique tuple `(repository_id, issue_number, comment_id, nonce)`. No
     new ledger or scheduler may be created.
   - Trusted host loads canonical Mission, WorkContract, Policy,
     ApprovalEngine and Kernel; existing CAB-01 verifies all applicable
     identities/scope/revocation, and a purpose-limited host tool allowlist.
   - Worker, Broker and approver run with separate non-admin OS principals;
     Keychain secrets remain Broker-only. Actual cross-UID access rejection
     is a separate real Mac gate, not a Python unit-test fact.
4. The existing bounded executor runs only a reviewed task type; **never**
   a raw shell string or a public Issue comment. Repeat the same gates on
   retry, crash recovery and resume. Commit no production changes.
5. Return an independently checked, sanitized receipt through the PRIVATE
   channel only. Raw evidence stays on the Mac. Issue #56 stays read-only.
6. Closing/revoking the private channel or credential must stop future
   dispatch. Verify stop/uninstall/replay denial before LaunchAgent deployment.

## Wire format: references only

The private comment body is UTF-8 JSON with exactly these keys:
`schema` (integer 1), `channel_repo_id`, `channel_issue_number`,
`mission_id`, `contract_id`, `approval_id`, `nonce`,
`signed_sha256`, `issued_at`, `expires_at`.

IDs contain only ASCII letters/digits/underscore/hyphen (6–96 chars).
The digest is 64 lowercase hexadecimal characters. Times are UTC Unix
seconds, with a maximum five-minute validity window. The body is limited
to 4096 bytes. It contains NO commands, prompt, source code, credentials,
log lines, personal metadata, local path or approval claims. Unknown
fields fail closed.

The transport inspector returns `TRANSPORT_ONLY_NOT_AUTHORIZED` even on
valid input. This string must **never** be interpreted as a PASS for any
runtime or authentication gate.

## Offline deterministic verification

```sh
python3 -m unittest discover -s tests/integrations -p 'test_private_channel_transport_v1.py' -v
```

The tests include synthetic positive parsing and rejection of public
repositories, swapped identities, stale/future requests, self-asserted
authority, duplicate JSON keys, shell fields, bad hashes and overlarge
inputs. Offline green tests would not imply a Mac Relay, Keychain, API
credential, signing, CAB-01 or unattended-runtime PASS.

## Remaining real integration gates

| Gate | Current status |
| --- | --- |
| Private channel exists with verified GitHub repository ID | BLOCKED / no accessible private repository currently verified |
| Broker-only minimum-scope credential provisioned in Keychain | NOT_EXECUTED |
| Real P3 signature + existing SQLite replay guard called per operation | NOT_INTEGRATED |
| CAB-01 canonical admission on dispatch/retry/resume | NOT_INTEGRATED |
| Distinct UID / Keychain cross-UID isolation on actual Mac | NOT_EXECUTED |
| Isolated allowed code-edit/test with independent receipt | NOT_EXECUTED |
| Local LaunchAgent start/stop/uninstall/recovery | NOT_EXECUTED |
| ChatGPT native MCP access | NOT_CONNECTED |
| New paid model API calls | NONE ISSUED in this change |

## Next local integration (only after native tools are available)

1. Snapshot the Mac's **entire** dirty `nexara-durable-upstream-review`
   working tree, including untracked files; preserve the two local
   `nexara.db` files separately. Patch-only backups are insufficient.
2. Inspect the existing P3 Broker interface and source before importing this
   contract into a separate reviewed local branch/worktree. Never overwrite
   its `integrations/mac-relay` directory or start the disabled service.
3. Provision or connect a private channel through trusted user GitHub UI,
   pin immutable repository/owner/issue IDs in Broker-only configuration.
4. Connect the inspector only as an **additional ingress precheck**; run
   existing P3 signature, lease/epoch and CAB-01 gates first for each side
   effect, including resume. Verify denial cases with independent tests.
5. Verify isolated Mac zero-cost test job + signed receipt returned to ChatGPT.
   Only after all Issue #63 hard gates pass consider a reversible non-admin
   user LaunchAgent.

No automatic public GitHub issue dispatch, remote arbitrary shell, new
credential, daemon, provider call or local Mac modification is implemented
in this PR.
