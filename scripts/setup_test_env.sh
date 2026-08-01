#!/bin/bash
# NEXARA PRIME Test Environment Setup
# Single entry point for reproducible test installation.
# Usage: bash scripts/setup_test_env.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "=== NEXARA PRIME Test Environment Setup ==="
echo "Python: $(python3 --version)"
echo "Repo:   $REPO_ROOT"
echo ""

python3 -m pip install -e '.[test]' -e platform/sdk/python

echo ""
echo "=== Setup Complete ==="
python3 -c "
import nexara_prime, nexara_sdk, pytest, httpx, yaml
print(f'nexara_prime: {nexara_prime.__file__}')
print(f'nexara_sdk:   {nexara_sdk.__file__}')
print(f'pytest:       {pytest.__version__}')
print(f'httpx:        {httpx.__version__}')
print(f'yaml:         OK')
print('All dependencies verified.')
"