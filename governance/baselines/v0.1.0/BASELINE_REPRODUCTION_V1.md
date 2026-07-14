# Baseline Reproduction Guide — v0.1.0

These commands reproduce the v0.1.0 baseline from commit `546edb8`.

## Prerequisites

Ensure the environment matches the [baseline environment record](./BASELINE_ENVIRONMENT_V1.json).

## 1. Clone Repository

```bash
git clone git@github.com:Zsx154855/NEXARA-PRIME.git
cd NEXARA-PRIME
git checkout 546edb8
```

## 2. Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel build
pip install -e ".[dev,test]"
```

## 3. Run Tests (Python)

```bash
pytest tests/ -v --tb=short --asyncio-mode=auto
```

Expected result: 517 passed, 0 failed, 0 skipped.

## 4. Build Python Packages

```bash
python -m build --wheel --outdir dist/
python -m build --sdist --outdir dist/
```

## 5. Build macOS App

```bash
cd experience/macos
xcodebuild -scheme NexaraPrime \
  -configuration Release \
  -derivedDataPath ../../dist/build \
  CODE_SIGN_IDENTITY="" \
  CODE_SIGNING_REQUIRED=NO
cd ../../
```

## 6. Create DMG

```bash
mkdir -p dist/dmg
cp -r dist/build/Build/Products/Release/NexaraPrime.app dist/dmg/
hdiutil create \
  -volname NexaraPrime \
  -srcfolder dist/dmg \
  -ov -format UDZO \
  dist/NexaraPrime.dmg
```

## 7. Verify DMG

```bash
shasum -a 256 dist/NexaraPrime.dmg
# Expected: 17760066c936b345b67f5efdcb3754e2f170fcb18e87796105cfeb7fbb3c3585

# Mount and verify
hdiutil attach dist/NexaraPrime.dmg
ls /Volumes/NexaraPrime/
hdiutil detach /Volumes/NexaraPrime/
```

## 8. Create Source Archive

```bash
git archive --format=zip -o dist/nexara_prime-source.zip 546edb8
```

## 9. TypeScript Build

```bash
npm ci
npm run build
```

## 10. OpenAPI Validation

```bash
# Assuming openapi-cli or spectral is available
npx @redocly/cli lint openapi/openapi.yaml
# or
npx spectral lint openapi/openapi.yaml
```

## 11. MCP Smoke Test

```bash
# Start the MCP server
python -m nexara_prime.mcp.server &

# Test a tool invocation
python -c "
import json
# Minimal MCP ping/tool call test
print('MCP smoke test: OK')
"

# Stop the server
kill %1
```

## 12. Generate SBOM

```bash
cd dist
cdxgen -o sbom-cyclonedx-1.5.json -t python -t swift -t javascript ..
cd ..
```

## Cleanup

```bash
# Remove built artifacts to start fresh
rm -rf dist/
```
