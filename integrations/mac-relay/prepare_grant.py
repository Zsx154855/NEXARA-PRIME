#!/usr/bin/env python3
"""Build the exact Mission Contract and unsigned Grant for one readonly-inspect task.

Prints the canonical objects and the one command the owner must run to sign.
It never touches a private key and never signs.
"""
import argparse
import datetime as dt
import json
import secrets
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import relay
from durable import digest
from p2_missions import task_from
from p2_workspace import Workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="absolute path of the isolated git workspace")
    parser.add_argument("--approver", default="owner-approver", help="approver principal name")
    parser.add_argument("--requester", default="b1-worker", help="worker principal name")
    parser.add_argument("--requester-uid", type=int, required=True)
    parser.add_argument("--instruction", default="Report the git HEAD and worktree status of this repository in one line.")
    parser.add_argument("--route-endpoint", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--public-key-file", help="approver public key, echoed into the grant bundle")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    tree = Workspace(workspace_path)
    # P3 authenticates the workspace *identity*, not its filesystem directory.
    # The directory is only used to construct the trusted Workspace instance.
    workspace_binding = tree.binding()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    nonce = secrets.token_hex(12)
    contract = {
        "contract_id": f"contract-dsh-{nonce}",
        "mission_id": f"mission-dsh-{nonce}",
        "requester_uid": args.requester_uid,
        "requester": args.requester,
        "approver": args.approver,
        "revision": 1,
        "workspace": workspace_binding,
        "head": tree.head(),
        "allowed_operations": ["dsh.task.run"],
        "expires_at": (now + dt.timedelta(minutes=30)).isoformat(),
        "status": "active",
        "max_seconds": 20,
        "budget_microusd": 0,
        "test_id": "p3-fixture-check",
    }
    payload = {
        "mission_id": contract["mission_id"], "task_id": f"task-dsh-{nonce}",
        "idempotency_key": f"idem-dsh-{nonce}", "operation": "dsh.task.run",
        "arguments": {
            "task_kind": "readonly-inspect",
            "instruction": args.instruction,
            "instruction_sha256": digest(args.instruction),
            "route": {"kind": "loopback-http", "endpoint": args.route_endpoint},
        },
    }
    task = task_from(payload, workspace_binding)
    grant = {
        "approval_id": f"approval-dsh-{nonce}", "principal": args.approver,
        "task_sha256": task.request_hash,
        "contract_sha256": digest(relay.json_canonical(contract)),
        "issued_at": now.isoformat(),
    }
    public_key = None
    if args.public_key_file:
        parts = Path(args.public_key_file).read_text().split()
        if len(parts) < 2 or parts[0] != "ssh-ed25519":
            parser.error("approver public key must be an ssh-ed25519 public key")
        public_key = " ".join(parts[:2])
    canonical_grant = relay.json_canonical(grant)
    bundle = {
        "contract": contract,
        "task": payload,
        "grant": grant,
        "approver_public_key": public_key,
        "sign_command": (
            "printf '%s' " + shlex.quote(canonical_grant) +
            ' | /usr/bin/ssh-keygen -Y sign -f "$HOME/.nexara-p3/approver/approver_ed25519"'
            " -n nexara-p3-approval"
        ),
        "canonical_grant": canonical_grant,
        "note": (
            "UNSIGNED. Owner must inspect the exact contract and task before signing "
            "interactively from a separate owner-controlled OS principal. "
            "Do not execute a grant until CAB and runtime gates pass."
        ),
    }
    print(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
