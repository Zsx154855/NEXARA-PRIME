#!/bin/sh
# P3 phase 1: isolated workspace + unsigned grant. Safe to run as the ordinary
# operator (agentos). It never creates, reads or runs anything with the Approver
# private key -- the key must live in a separate owner-only macOS account.
#
# Usage: sh prepare_mission.sh /path/to/approver_ed25519.pub
set -eu
PUB="${1:-}"
[ -n "$PUB" ] || { echo "usage: sh $0 /path/to/approver_ed25519.pub" >&2; exit 2; }
[ -f "$PUB" ] || { echo "ABORT: public key not found: $PUB" >&2; exit 2; }

ROOT="${NEXARA_P3_ROOT:-$HOME/.nexara-p3}"
WS="$ROOT/workspace"
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
  printf 'NEXARA isolated mission workspace\n' > README.txt
  /usr/bin/git add README.txt
  /usr/bin/git -c user.name="NEXARA isolated" -c user.email="isolated@nexara.local" commit -qm "isolated baseline"
fi
chmod 700 "$WS"
echo "workspace : $WS"
echo "head      : $(cd "$WS" && /usr/bin/git rev-parse HEAD)"
echo "public key: $(/usr/bin/ssh-keygen -lf "$PUB" | /usr/bin/awk '{print $2}')"

"$PY" "$RELAY/prepare_grant.py" \
  --workspace "$WS" \
  --requester-uid "$UID_NOW" \
  --public-key-file "$PUB" \
  > "$ROOT/unsigned-grant.json"
chmod 600 "$ROOT/unsigned-grant.json"

"$PY" - "$ROOT/unsigned-grant.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d["contract"]
print()
print("mission    : " + c["mission_id"])
print("operation  : " + ",".join(c["allowed_operations"]))
print("max_seconds: " + str(c["max_seconds"]))
print("expires_at : " + c["expires_at"] + "   <-- sign and run before this")
print("budget     : " + str(c["budget_microusd"]) + " microusd")
print()
print("bundle     : " + sys.argv[1] + "  (unsigned)")
print()
print("--- sign this in the OWNER-ONLY account, copy the signature back ---")
print('/usr/bin/ssh-keygen -Y sign -f "$HOME/.nexara-p3/approver/approver_ed25519" -n nexara-p3-approval')
print()
print("exact bytes to feed that command on stdin:")
print(d["sign_command"].replace(" | /usr/bin/ssh-keygen", "").replace("printf '%s' ", "").strip("'"))
PY
