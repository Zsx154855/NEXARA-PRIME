# G10 — Local Release Evidence

**Date:** 2026-07-14T20:52:15Z
**head:** 4cb3cd3
**Status:** LOCAL_RELEASE_READY

## DMG Verification

- **File:** dist/NexaraMac-0.1.0-unsigned.dmg
- **Size:** 571,870 bytes
- **SHA-256:** 17760066c936b345b67f5efdcb3754e2f170fcb18e87796105cfeb7fbb3c3585
- **Mount:** VERIFIED — mounted on /Volumes/NEXARA PRIME, NexaraMac.app executable present
- **App Bundle:** dist/NexaraMac.app, Info.plist valid (plutil OK), launch via open verified

## All Artifact Hashes

| Artifact | SHA-256 |
|----------|---------|
| NexaraMac-0.1.0-unsigned.dmg | 17760066c936b345b67f5efdcb3754e2f170fcb18e87796105cfeb7fbb3c3585 |
| NexaraMac-0.1.0-unsigned.zip | 622c606e37fb0d8df14a84db8997f76dd8df606096e7fb9153eac6c7688545c4 |
| NexaraMac binary (in .app) | 015e94aebf4d27cf452055bee791e558ef543c0617b46925d07cdad24c32d18f |
| nexara_prime-0.1.0-py3-none-any.whl | 24858845d0113a3032a260602a6ad094522247808b90d02a90daebfe8b25f4a6 |
| nexara_prime-0.1.0.tar.gz | aec33c362cde51fc37c54f5fb56cfb918da0c4812457f93a37c115cfb7779c9e |
| sbom-0.1.0.json | 355f60033cc33597aa8eb711f600cc07761172a595a9308b5b94ffa731e5db02 |

## Build Verification

- Python full regression: 517 passed, 0 failed
- macOS Swift build: clean, arm64 1.1MB
- TypeScript SDK: npm ci + tsc --noEmit PASS
- App Bundle validation: plutil lint OK, open launch verified
- MCP server: 6 tools, health smoke test PASS

## SBOM

- **Format:** CycloneDX 1.5
- **Components:** 8 (fastapi, pydantic, uvicorn, nexara-sdk, nexara-sdk-typescript, NexaraCore, NexaraMac, NexaraIOS)
- **File:** dist/sbom-0.1.0.json

## External Distribution Blockers

- macOS code signing certificate (Apple Developer Program)
- macOS notarization (Apple notary service)
- iOS Provisioning Profile (Apple Developer Program)
- git push / git tag (human release authorization)
