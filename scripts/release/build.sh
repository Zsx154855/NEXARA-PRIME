#!/usr/bin/env bash
# Build release artifacts: wheel, container image, SBOM, checksums.
#   bash scripts/release/build.sh [--image TAG]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
PY="${NEXARA_PYTHON:-python3}"
VERSION="$("$PY" -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
IMAGE="${2:-nexara-prime}"
DIST="$ROOT/dist"
rm -rf "$DIST" && mkdir -p "$DIST"

echo "== wheel (version $VERSION) =="
"$PY" -m pip wheel . -w "$DIST" --no-deps -q

echo "== container image =="
docker build -q -t "$IMAGE:$VERSION" -t "$IMAGE:latest" .

echo "== sbom =="
docker run --rm --entrypoint python "$IMAGE:$VERSION" -m pip freeze \
  | "$PY" scripts/release/sbom.py > "$DIST/SBOM.cdx.json"

echo "== image tarball =="
docker save "$IMAGE:$VERSION" | gzip -c > "$DIST/$IMAGE-$VERSION-image.tar.gz"

echo "== checksums =="
( cd "$DIST" && sha256sum * > SHA256SUMS )

echo
echo "artifacts in $DIST:"
ls -1 "$DIST"
echo "version: $VERSION"
