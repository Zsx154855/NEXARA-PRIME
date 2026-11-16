#!/bin/bash
# Zero-cost Mac smoke: does NOT register a runner, touch secrets or sign as independent QA.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)" || exit 1
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)" || exit 1
TARGET="/Users/agentos/Worktrees/NEXARA-PR76-ONESHOT-QA-20261115"
EVIDENCE="/Users/agentos/Documents/NEXARA-PR76-QA-xYmq0y"
POLICY="$ROOT/docs/qa-sidecar-pr76.example-policy.json"
OUTDIR="$(mktemp -d "$HOME/Documents/NEXARA-QA-SIDECAR-MAC-XXXXXX")" || exit 1
mkdir -p "$OUTDIR"
printf 'EVIDENCE_DIR=%s\n' "$OUTDIR"
command -v git >/dev/null || { echo 'MAC_SMOKE=BLOCKED_GIT'; exit 1; }
command -v ssh-keygen >/dev/null || echo 'SIGNATURE_TEST=SKIP_NO_SSH_KEYGEN'
command -v python3 >/dev/null || { echo 'MAC_SMOKE=BLOCKED_PYTHON'; exit 1; }
python3 -m unittest discover -s "$ROOT/tests" -p test_qa_sidecar_mvp.py -v \
  > "$OUTDIR/unit.log" 2>&1
UNIT_RC=$?
tail -n 9 "$OUTDIR/unit.log"
printf 'UNIT_EXIT=%s\n' "$UNIT_RC"
if [ "$UNIT_RC" -ne 0 ]; then
  echo 'MAC_SMOKE=BLOCKED_UNIT_TESTS'
  exit "$UNIT_RC"
fi
# This is an untrusted demo policy. Its digest is not an external trust anchor.
cp "$POLICY" "$OUTDIR/demo.policy.json" || exit 1
POLICY_SHA="$(shasum -a 256 "$OUTDIR/demo.policy.json" | awk '{print $1}')"
python3 "$ROOT/scripts/qa_sidecar/verify.py" \
  --repo "$TARGET" --evidence "$EVIDENCE" \
  --policy "$OUTDIR/demo.policy.json" --policy-sha256 "$POLICY_SHA" \
  --statement-out "$OUTDIR/statement.json" \
  > "$OUTDIR/verify.json" 2> "$OUTDIR/verify.error.log"
VERIFY_RC=$?
cat "$OUTDIR/verify.json"
if [ "$VERIFY_RC" -ne 2 ]; then
  echo "MAC_SMOKE=BLOCKED_EVIDENCE VERIFY_EXIT=$VERIFY_RC"
  cat "$OUTDIR/verify.error.log"
  exit 1
fi
grep -q '"gate": "QA_BLOCKED"' "$OUTDIR/verify.json" || exit 1
echo 'MAC_SMOKE=TECHNICAL_PASS_IDENTITY_BLOCKED'
echo 'INDEPENDENT_QA=NOT_VERIFIED'
echo "EVIDENCE_DIR=$OUTDIR"
exit 0
