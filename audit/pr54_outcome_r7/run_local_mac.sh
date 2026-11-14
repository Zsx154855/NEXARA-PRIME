#!/usr/bin/env bash
# NEXARA-PRIME PR54 outcome admission: isolated, zero-paid-model, no-prod test.
# Existing R6 Mac checkout and Python 3.12 venv are reused. No pip or merge.
set -uo pipefail

ROOT="${NCA_R6_ROOT:-/var/folders/f2/4t74_j890z77bg1bntw_90d40000gn/T/nca01-r6-pt7oT9e7}"
REPO="$ROOT/repo"
WORK="$ROOT/pr54-outcome-r7"
BRANCH="audit/pr54-business-outcome-admission-r1-20261114"
BASE="103c79f500c522492815f9b86dfa0fb80dd07e30"
EXPECTED="fb2f60e65a60f6c3a90cc3475c6a82685ab4240e"
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
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "BLOCKED: unexpected patch SHA (requires re-review)"; exit 2
fi

if [ -d "$WORK" ]; then
  [ "$(git -C "$WORK" rev-parse HEAD 2>/dev/null)" = "$EXPECTED" ] || {
    echo "BLOCKED: existing worktree is not the approved SHA"; exit 2;
  }
else
  git -C "$REPO" worktree add -q --detach "$WORK" "$EXPECTED" || exit 2
fi
[ "$(git -C "$WORK" rev-parse HEAD)" = "$EXPECTED" ] || exit 2
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
echo "PR54_FIX_HEAD=$EXPECTED"
echo "N01_9_REGRESSION_EXIT=$N01_RC"
echo "R7_OUTCOME_CONTRACT_EXIT=$R7_RC"
echo "UNCHANGED_R6_CONTRACT_EXIT=$R6_RC"
echo "POST_TEST_WORKTREE_STATUS=$(git status --porcelain | wc -l | tr -d ' ')"
for name in r7-n01 r7-outcome r7-original-r6; do
  echo "--- $name ---"
  tail -n 70 "$ROOT/$name.log"
done
echo "=== END R7 LOCAL GATE ==="
