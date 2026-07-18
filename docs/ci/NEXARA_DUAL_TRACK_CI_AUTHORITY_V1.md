# NEXARA Dual-Track CI Authority V1

## Goal

Establish dual-track verification: GitHub-hosted CI (when billing allows) + local evidence-driven authority with cryptographic receipts. The project must not halt development due to GitHub billing issues.

## Architecture

### Track A: GitHub Control Plane
- `ci.yml` — formal required checks (python, typescript, swift-macos, swift-ios, governance, secret-scan)
- `self-hosted-probe.yml` — isolated workflow_dispatch probe using a repository-level self-hosted runner (label: `nexara-ci-probe-arm64`) to test whether the GitHub control plane can dispatch to a self-hosted runner despite billing lock

### Track B: Local CI Authority
- `scripts/ci/nexara_ci_authority.py` — mirrors the formal ci.yml contract, runs all checks locally, generates cryptographic receipts
- `scripts/ci/verify_receipt.py` — verifies receipt integrity: log hashes, payload hash, HEAD, hash chain
- `scripts/ci/check_*.sh` — individual check scripts for direct invocation

## Self-Hosted Probe Scope
- Does NOT automatically run PR code on a personal Mac
- Does NOT install as a persistent service
- Only `workflow_dispatch` (manual trigger)
- Precise runner label (`nexara-ci-probe-arm64`) prevents accidental job routing
- Repository-level scope only

## Local Authority Architecture
- Writer: `nexara_ci_authority.py` executes checks, generates receipt
- Verifier: `verify_receipt.py` independently re-verifies all hashes and logs
- Auditor: manual review of receipt + log index
- All evidence stored in `.runtime/ci/` (gitignored, never committed)

## Status Model
- PASS: all applicable checks pass
- FAIL: any applicable check fails
- CONDITIONAL_PASS: all applicable checks pass but some are NOT_APPLICABLE
- ERROR: authority itself failed (missing logs, hash mismatch, etc.)

## Local PASS != GitHub PASS
Local Authority PASS confirms the code-base contract is met locally. It does NOT claim GitHub required checks are green. Owner retains final Mark Ready / Merge authority.

## Ruff Pre-existing Debt
`ruff check src tests` includes 1228 lines of pre-existing issues in modules not modified by the integration train. The authority correctly reports FAIL. This debt is tracked as a separate quality program candidate.

## iOS NOT_APPLICABLE
The `experience/ios` directory contains only `Package.swift` (SPM), no `.xcodeproj`. The ci.yml uses `xcodebuild` which requires `.xcodeproj`. Swift build works but does not produce an iOS simulator binary. This is a CI configuration gap, not a code defect.

## Governance Script Contract
`detect_state_drift.py` exits 0 even when drift is detected on work branches. Its contract is non-blocking on non-main branches. The authority reports FAIL when drift exits non-zero.

## Runner Security Model
- Dedicated low-privilege macOS user recommended for long-term runners
- Separate machine or isolated VM
- Never receive public fork PRs automatically
- Dedicated labels only
- No persistent secrets
- Short-lived work directories
- Periodic rebuild

## Billing Recovery Sequence
1. Owner resolves billing issue
2. Re-run GitHub CI on PR #13 HEAD
3. Classify real failures (platform/env/dep/config/code/pre-existing)
4. One unified fix commit
5. All 6 jobs green → Owner approves Mark Ready → Owner approves Merge

## Unacceptable Bypasses
- `|| true`, `|| echo`, `continue-on-error` to swallow failures
- Narrowing ruff scope to make CI green
- Claiming local PASS as GitHub green
- Disabling governance or secret-scan checks
- Force push or amend on pushed commits

## Version Limits
- V1: local authority only; no GitHub required-check integration
- Self-hosted runner not persistent; probe only
- Receipt hash chain starts at FIRST_RECEIPT (no prior history)
