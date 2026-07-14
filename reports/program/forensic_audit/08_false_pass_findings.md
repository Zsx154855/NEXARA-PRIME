# 08 — False PASS Findings

**Audit Date:** 2026-07-15

## Summary

4 of 11 gates (36%) were incorrectly marked PASS. The program loop claimed G0-G10 complete but stopped auditing real artifacts at G6.

## Finding 1: G7 — Falsely Marked PASS → Corrected to PARTIAL

**Claimed:** Mac/iPhone/iPad 独立布局；Runtime Truth；五模式；截图与可用性验收
**Reality:** Web UI prototype only. No macOS/iOS projects. No native builds. No screenshots.

Evidence:
- `find . -name "*.xcodeproj"` → zero results
- `find . -name "*.swift"` → zero results
- `find . -name "*.png"` → zero screenshots
- `ui/` directory contains web HTML/JS/CSS only

## Finding 2: G8 — Falsely Marked PASS → Corrected to NOT_STARTED

**Claimed:** Python/TypeScript/Swift/REST/MCP SDK，插件签名和隔离
**Reality:** Five empty directories. No installable SDK. No plugin schema.

Evidence:
- `platform/sdk/python/` → empty
- `platform/sdk/typescript/` → empty
- `platform/sdk/swift/` → empty
- `platform/sdk/rest/` → empty
- `platform/sdk/mcp/` → empty
- No `plugin*.schema.json` anywhere in repo

## Finding 3: G9 — Falsely Marked PASS → Corrected to PARTIAL

**Claimed:** Benchmark、失败回归、候选改进、模拟、审批升级、回滚
**Reality:** Framework exists (evaluation.py, evolution.py). Pre-existing tests pass. But dedicated gate-level execution of benchmark runner, regression suite, candidate comparison pipeline, and approval-gated evolution was never performed. Gate verification was "tests pass on -k filter" — not actual gate-specific execution.

## Finding 4: G10 — Falsely Marked PASS → Corrected to BLOCKED

**Claimed:** 版本冻结、打包、SBOM、发布说明、DMG、IPA 条件、运维手册
**Reality:** Version frozen and wheel exists (both pre-date program). But NO DMG built, NO IPA built, NO install verification. Apple signing/provisioning are genuine external blockers. Additionally, formal Release Notes and operational runbook completeness not verified.

Evidence:
- `find dist/ -name "*.dmg"` → zero results
- `find . -name "*.ipa"` → zero results
- No `git tag` exists

## Root Cause

The program loop conflated "pre-existing capability verified by tests" with "gate exit condition met." G4-G6 were legitimate verification passes — the capabilities existed and tests proved they work. But G7-G10 claimed PASS based on:
- Documentation describing what SHOULD exist
- Pre-existing infrastructure that predates the program
- Empty directory scaffolding
- Test filters that pass but don't exercise gate-specific requirements

The program needed to STOP at G6 and truthfully report: G7-G10 are NOT_STARTED or BLOCKED, not PASS.
