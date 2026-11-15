#!/bin/sh
# Owner-only Approver key bootstrap. The private key never leaves your shell.
# Usage: sh approver_bootstrap.sh [target-dir]
set -eu
DIR="${1:-$HOME/.nexara-p3/approver}"
[ -e "$DIR" ] && { echo "ABORT: $DIR already exists"; exit 1; }
mkdir -p "$DIR"
chmod 700 "$DIR"
/usr/bin/ssh-keygen -q -t ed25519 -N "" -C "nexara-p3-approver" -f "$DIR/approver_ed25519"
chmod 600 "$DIR/approver_ed25519"
chmod 644 "$DIR/approver_ed25519.pub"
echo "private key: $DIR/approver_ed25519  (0600, never copy it anywhere)"
echo "public key :"
cat "$DIR/approver_ed25519.pub"
echo "fingerprint: $(/usr/bin/ssh-keygen -lf "$DIR/approver_ed25519.pub" | awk '{print $2}')"
echo
echo "Register ONLY the public key. The attester key must differ."
