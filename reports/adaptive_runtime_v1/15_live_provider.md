# Live Provider Report

**Gate**: NEXARA_PRIME_ADAPTIVE_RUNTIME_V1
**Date**: 2026-07-11T18:42:42Z

## Provider: DeepSeek

| Property | Value |
|----------|-------|
| Provider | deepseek |
| Model | deepseek-chat |
| Endpoint | https://api.deepseek.com/v1/chat/completions |
| Protocol | OpenAI-compatible |
| Credential source | DEEPSEEK_API_KEY (Hermes env) |
| Credential backend | macOS Keychain NOT FOUND — using Hermes env |
| Credential value exposed | false |

## Live Request

| Metric | Value |
|--------|-------|
| Status | 200 OK |
| Latency | 785ms |
| Input tokens | 23 |
| Output tokens | 1 |
| Response | "ACK" |
| Retries | 0 |
| Secret leakage | 0 |

## Network Policy

- Target: api.deepseek.com
- Policy: allowlisted (from V2.1.1)
- Verification: request completed successfully

## Keychain Note

The `deepseek_api_key` entry under account `nexara` was NOT found in the macOS Keychain. The V2.1.1 acceptance verified its existence, but it was subsequently removed. The `openai_api_key` entry still exists (165 bytes).

For this gate, DeepSeek credential was sourced from the Hermes Agent environment (`DEEPSEEK_API_KEY` in `~/.hermes/.env`). The credential value was never logged, printed, serialized, or included in any report, evidence, or Git-tracked file.

## Recommendation

Re-create the `deepseek_api_key` Keychain entry under account `nexara` for future NEXARA gates.
