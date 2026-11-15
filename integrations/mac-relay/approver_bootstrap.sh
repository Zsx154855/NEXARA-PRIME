#!/bin/sh
# Interactive, owner-only Approver bootstrap. NEVER run in an agent-controlled shell.
# Usage (in a separate owner-controlled macOS account): sh approver_bootstrap.sh [target-dir]
set -eu
umask 077

if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "ABORT: an interactive owner-operated terminal is required" >&2
  exit 1
fi
OPERATOR=$(/usr/bin/id -un)
case "$OPERATOR" in
  root|agentos|nexara-broker|nexara-worker)
    echo "ABORT: $OPERATOR is not an independent owner-only signing identity" >&2
    exit 1
    ;;
esac

DIR="${1:-$HOME/.nexara-p3/approver}"
if [ -e "$DIR" ] || [ -L "$DIR" ]; then
  echo "ABORT: destination already exists; never overwrite an Approver key: $DIR" >&2
  exit 1
fi
mkdir -m 700 -p "$DIR"
chmod 700 "$DIR"
TMP=$(/usr/bin/mktemp -d "$DIR/.keygen.XXXXXXXX")
cleanup() {
  /bin/rm -f "$TMP/approver_ed25519" "$TMP/approver_ed25519.pub"
  /bin/rmdir "$TMP" 2>/dev/null || true
}
trap cleanup 0

echo "Creating a new Ed25519 key. Enter a STRONG NON-EMPTY passphrase privately."
echo "Do not use an agent-controlled account or paste the passphrase into chat."
/usr/bin/ssh-keygen -q -t ed25519 -C "nexara-p3-approver" -f "$TMP/approver_ed25519"
if /usr/bin/ssh-keygen -y -P "" -f "$TMP/approver_ed25519" >/dev/null 2>&1; then
  echo "ABORT: empty passphrase is forbidden. No usable key was installed." >&2
  exit 1
fi
/bin/mv "$TMP/approver_ed25519" "$DIR/approver_ed25519"
/bin/mv "$TMP/approver_ed25519.pub" "$DIR/approver_ed25519.pub"
chmod 600 "$DIR/approver_ed25519"
chmod 644 "$DIR/approver_ed25519.pub"
echo "Owner-only key created. Register ONLY the public key after verifying role separation."
echo "Public key:"
/bin/cat "$DIR/approver_ed25519.pub"
echo "Fingerprint: $(/usr/bin/ssh-keygen -lf "$DIR/approver_ed25519.pub" | /usr/bin/awk '{print $2}')"
echo "CAUTION: file permissions and a passphrase alone cannot isolate a key from agents running as this same OS user."
