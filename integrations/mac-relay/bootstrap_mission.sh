#!/bin/sh
# One command: prepare the isolated workspace, the owner approver key and the unsigned grant.
# Everything except the final signature. The private key is created here, in your shell,
# and is never read by the agent.
set -eu
ROOT="${NEXARA_P3_ROOT:-$HOME/.nexara-p3}"
WS="$ROOT/workspace"
KEYDIR="$ROOT/approver"
RELAY="$(cd "$(dirname "$0")" && pwd)"
PY=/opt/homebrew/bin/python3.12
UID_NOW=$(/usr/bin/id -u)

mkdir -p "$ROOT"
chmod 700 "$ROOT"

if [ ! -d "$WS/.git" ]; then
  mkdir -p "$WS"
  chmod 700 "$WS"
  cd "$WS"
  /usr/bin/git init -q --template=
  printf 'NEXARA isolated mission workspace
' > README.txt
  /usr/bin/git add README.txt
  /usr/bin/git -c user.name="NEXARA isolated" -c user.email="isolated@nexara.local" commit -qm "isolated baseline"
fi
echo "workspace: $WS"
echo "head     : $(cd "$WS" && /usr/bin/git rev-parse HEAD)"

if [ ! -f "$KEYDIR/approver_ed25519" ]; then
  sh "$RELAY/approver_bootstrap.sh" "$KEYDIR"
else
  echo "approver key already present: $KEYDIR/approver_ed25519"
  echo "public key: $(cat "$KEYDIR/approver_ed25519.pub")"
fi

echo
echo "=== unsigned grant, ready for your signature ==="
"$PY" "$RELAY/prepare_grant.py" \
  --workspace "$WS" \
  --requester-uid "$UID_NOW" \
  --public-key-file "$KEYDIR/approver_ed25519.pub" \
  > "$ROOT/unsigned-grant.json"
echo "written: $ROOT/unsigned-grant.json"
echo
echo "=== sign it (one line, your key, your shell) ==="
"$PY" - "$ROOT/unsigned-grant.json" <<'PY'
import json, sys
bundle = json.load(open(sys.argv[1]))
print("cd /tmp && printf '%s' " + repr(bundle["canonical_grant"]) +
      " | /usr/bin/ssh-keygen -Y sign -f " + str(__import__("pathlib").Path.home() / ".nexara-p3/approver/approver_ed25519") +
      " -n nexara-p3-approval - > " + str(__import__("pathlib").Path.home() / ".nexara-p3/grant.sig"))
PY
