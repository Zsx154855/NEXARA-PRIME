"""Probe macOS kernel denial against synthetic files and a loopback listener."""

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile


with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
    root = Path(directory).resolve()
    secret = root / "private_fixture"
    secret.write_text("synthetic")
    alias = root / "alias"
    alias.symlink_to(secret)
    allowed = root / "summary_fixture"
    allowed.write_text("synthetic")
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    policy = (
        "(version 1) (allow default) "
        f"(deny file-read-data file-write* (literal {json.dumps(str(secret))})) "
        "(deny network-outbound)"
    )
    probe = """
from pathlib import Path
import json, socket, sys
secret, alias, allowed = map(Path, sys.argv[1:4])
def blocked(operation):
    try:
        operation()
    except PermissionError:
        return True
    return False
assert allowed.read_text() == 'synthetic'
result = {
    'fixture_direct_read_denied': blocked(secret.read_bytes),
    'fixture_symlink_read_denied': blocked(alias.read_bytes),
    'fixture_write_denied': blocked(lambda: secret.write_text('changed')),
    'loopback_outbound_denied': blocked(lambda: socket.create_connection(('127.0.0.1', int(sys.argv[4])), 2)),
    'allowed_summary_read': True,
}
print(json.dumps(result))
assert all(result.values())
"""
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", policy, sys.executable, "-I", "-B", "-c", probe,
         str(secret), str(alias), str(allowed), str(listener.getsockname()[1])],
        capture_output=True, text=True, timeout=12,
    )
    if result.returncode:
        print(json.dumps({"status": "BLOCKED" if "sandbox_apply" in result.stderr else "FAIL",
                          "kernel_fixture_only": True, "dedicated_account": False}))
        sys.exit(2)
    print(json.dumps({**json.loads(result.stdout), "status": "PASS",
                      "kernel_fixture_only": True, "dedicated_account": False}))
