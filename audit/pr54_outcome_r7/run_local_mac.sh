#!/usr/bin/env bash
# NEXARA-PRIME PR54 outcome admission: isolated, zero-paid-model, no-prod test.
# Existing R6 Mac checkout and Python 3.12 venv are reused. No pip or merge.
set -uo pipefail

ROOT="${NCA_R6_ROOT:-/var/folders/f2/4t74_j890z77bg1bntw_90d40000gn/T/nca01-r6-pt7oT9e7}"
REPO="$ROOT/repo"
WORK="$ROOT/pr54-outcome-r7"
BRANCH="audit/pr54-business-outcome-admission-r1-20261114"
BASE="103c79f500c522492815f9b86dfa0fb80dd07e30"
EXPECTED_SOURCE_BLOB="467d5ed5727941e622a65441be9b58f1f7156ce5"
EXPECTED_TEST_BLOB="78b2cc23b4d7474dd0f634c646628617ab512e31"
EXPECTED_N01_BLOB="6e0e1e25b19c1ad5cd843db1ddae33adcce68c59"
PY="$ROOT/venv/bin/python"

echo "=== NEXARA PR54 R7 READONLY TEST GATE ==="
if [ ! -d "$REPO/.git" ] || [ ! -x "$PY" ]; then
  echo "ENV_BLOCKED: R6 source or isolated Python missing"; exit 2
fi
if [ "$(git -C "$ROOT/pr54" rev-parse HEAD 2>/dev/null)" != "$BASE" ]; then
  echo "ENV_BLOCKED: original PR54 source identity changed"; exit 2
fi
if [ "$(df -Pk "$ROOT" | awk 'NR==2{print $4}')" -lt 1048576 ]; then
  echo "ENV_BLOCKED: less than 1GiB free on audit volume"; exit 2
fi

# Fetch only the already authorized isolated branch. Never checkout main or
# modify the original PR54 worktree.
git -C "$REPO" fetch --no-tags --depth=1 origin "$BRANCH" || {
  echo "ENV_BLOCKED: unable to fetch isolated patch"; exit 2;
}
ACTUAL="$(git -C "$REPO" rev-parse FETCH_HEAD)" || exit 2
echo "FIX_BRANCH_HEAD=$ACTUAL"
for pair in \
  "src/nexara_prime/brain/experience_store.py:$EXPECTED_SOURCE_BLOB" \
  "tests/brain/test_n01_outcome_admission_r7.py:$EXPECTED_TEST_BLOB" \
  "tests/brain/test_n01_experience_persistence.py:$EXPECTED_N01_BLOB"; do
  file="${pair%%:*}"; expected_blob="${pair#*:}"
  actual_blob="$(git -C "$REPO" rev-parse "FETCH_HEAD:$file" 2>/dev/null)" || exit 2
  if [ "$actual_blob" != "$expected_blob" ]; then
    echo "BLOCKED: unexpected source/test blob: $file"; exit 2
  fi
done

if [ -d "$WORK" ]; then
  [ "$(git -C "$WORK" rev-parse HEAD 2>/dev/null)" = "$ACTUAL" ] || {
    echo "BLOCKED: existing worktree is not the verified branch SHA"; exit 2;
  }
else
  git -C "$REPO" worktree add -q --detach "$WORK" "$ACTUAL" || exit 2
fi
[ "$(git -C "$WORK" rev-parse HEAD)" = "$ACTUAL" ] || exit 2
cd "$WORK" || exit 2
export PYTHONPATH="$WORK/src"
export PYTHONDONTWRITEBYTECODE=1

"$PY" -c 'import pytest, pydantic, nexara_prime.brain.experience_store as e; print("PRODUCT_IMPORTED_FROM="+e.__file__)' || exit 2
echo "SOURCE_IDENTITY_VERIFIED=YES"
echo "PRE_TEST_WORKTREE_STATUS=$(git status --porcelain | wc -l | tr -d ' ')"

# Tests are separate so that an expected red contract does not hide other
# regression results. Old R6 durability asserts success from a health probe,
# which is deliberately invalid under the stricter business outcome contract.
N01_RC=0
"$PY" -m pytest -c "$WORK/pyproject.toml" -p no:cacheprovider \
  tests/brain/test_n01_experience_persistence.py \
  -q -ra --tb=short > "$ROOT/r7-n01.log" 2>&1 || N01_RC=$?
R7_RC=0
"$PY" -m pytest -c "$WORK/pyproject.toml" -p no:cacheprovider \
  tests/brain/test_n01_outcome_admission_r7.py \
  -q -ra --tb=short > "$ROOT/r7-outcome.log" 2>&1 || R7_RC=$?
R6_RC=0
"$PY" -m pytest -c "$WORK/pyproject.toml" -p no:cacheprovider --import-mode=importlib \
  "$REPO/audit/nca01_r6/test_nca01_pr54_true_stack.py" \
  -q -ra --tb=short > "$ROOT/r7-original-r6.log" 2>&1 || R6_RC=$?

echo "=== REAL MAC TEST OUTPUT ==="
echo "PR54_FIX_HEAD=$ACTUAL"
echo "N01_9_REGRESSION_EXIT=$N01_RC"
echo "R7_OUTCOME_CONTRACT_EXIT=$R7_RC"
echo "UNCHANGED_R6_CONTRACT_EXIT=$R6_RC"
echo "POST_TEST_WORKTREE_STATUS=$(git status --porcelain | wc -l | tr -d ' ')"
for name in r7-n01 r7-outcome r7-original-r6; do
  echo "--- $name ---"
  tail -n 70 "$ROOT/$name.log"
done
echo "=== END R7 LOCAL GATE ==="
if [ "$N01_RC" -ne 0 ] || [ "$R7_RC" -ne 0 ]; then
  echo "R7_REQUIRED_COMPONENT_TESTS=FAIL"
  exit 1
fi
echo "R7_REQUIRED_COMPONENT_TESTS=PASS"
echo "TRUSTED_INDEPENDENT_QA=NOT_VERIFIED"
