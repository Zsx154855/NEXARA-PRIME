# NEXARA PRIME Provider Credential Live Acceptance V2.1.1

- Overall: **PASS**
- Secure Platform key creation: **PASS**
- Local ignored env destination: **PASS** (`.env.local`, mode `0600`)
- macOS Keychain backends: **PASS** (`openai_api_key`, `deepseek_api_key`)
- DeepSeek Keychain live read: **PASS**
- DeepSeek live provider request: **PASS**
- Provider protocol: **OpenAI-compatible**
- Provider model: **deepseek-v4-flash**
- Token accounting: **21 input / 38 output**
- Provider network target: **api.deepseek.com**
- Actual secret matches in Git-tracked files: **0**
- Existing tests: **298/298 PASS**
- Wheel build: **PASS**
- Browser E2E: **PASS**
- OS Sandbox: **PASS**
- Mission A/B/C, Audit and Recovery: **PASS**

## Decision

The live-provider Gate is accepted. DeepSeek was retrieved from macOS Keychain and completed a real OpenAI-compatible request through NEXARA's deny-by-default network policy. Runtime usage metadata was recorded and no secret entered reports, traces, evidence, or tracked files.

## Provider status

- DeepSeek: **LIVE VERIFIED**
- OpenAI: **CREDENTIAL VERIFIED / API QUOTA BLOCKED**

## Credential hygiene note

The connector's first successful creation returned only a safe summary and did not expose the encrypted payload to the local-save step. A second key creation was required to complete secure local storage. Revoke the older duplicate `Codex` key in OpenAI Platform and retain the most recently created key.
