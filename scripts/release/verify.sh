#!/usr/bin/env bash
# Verify a release directory: every artifact matches SHA256SUMS.
set -euo pipefail
DIR="${1:-dist}"
cd "$DIR"
sha256sum -c SHA256SUMS
