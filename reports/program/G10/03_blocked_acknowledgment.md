# G10 — RC 与发布闭环 (BLOCKED)

**Gate:** G10 — RC 与发布闭环
**Status:** BLOCKED
**Date:** 2026-07-15

## What Exists

| Item | Status |
|------|--------|
| Version frozen | ✅ 0.1.0 |
| Wheel | ✅ `nexara_prime-0.1.0-py3-none-any.whl` (69KB) |
| Python SDK wheel | ✅ `nexara_sdk-0.1.0-py3-none-any.whl` |
| SBOM | ✅ pyproject.toml |
| Test baseline | ✅ 508/508 |
| Ops manual | ✅ docs/12-Operations/ |

## Blocked By

| Blocker | Type | Resolution |
|---------|------|-----------|
| macOS code signing certificate | Apple Developer | Human: obtain cert via Apple Developer Program |
| Apple Provisioning Profile | Apple Developer | Human: create profile in App Store Connect |
| DMG generation | Build | Unblocked once signing cert available |
| IPA output | Build | Unblocked once Provisioning Profile available |
| `git push` | Release | Human: authorize push |
| `git tag v0.1.0` | Release | Human: authorize tag |
| Product brand name | Business | Human: decide product name |

## Verdict

BLOCKED — all code artifacts exist (wheel, SDK, tests). Release blocked by external Apple Developer credentials and human release authorization. This is the correct terminal state per Constitution: "release actions require human approval."
