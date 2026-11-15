#!/usr/bin/env python3
"""Build the exact Mission Contract and unsigned Grant for one readonly-inspect task.

Prints the canonical objects and the one command the owner must run to sign.
It never touches a private key and never signs.
"""
import argparse
import datetime as dt
import json
import subprocess
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

    workspace = str(Path(args.workspace).resolve())
    tree = Workspace(Path(workspace))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    contract = {
        "contract_id": "contract-dsh-readonly-1",
        "mission_id": "mission-dsh-readonly-1",
        "requester_uid": args.requester_uid,
        "requester": args.requester,
        "approver": args.approver,
        "revision": 1,
        "workspace": workspace,
        "head": tree.head(),
        "allowed_operations": ["dsh.task.run"],
        "expires_at": (now + dt.timedelta(minutes=30)).isoformat(),
        "status": "active",
        "max_seconds": 20,
        "budget_microusd": 0,
        "test_id": "p3-fixture-check",
    }
    payload = {
        "mission_id": contract["mission_id"], "task_id": "task-dsh-readonly-1",
        "idempotency_key": "idem-dsh-readonly-1", "operation": "dsh.task.run",
        "arguments": {
            "task_kind": "readonly-inspect",
            "instruction": args.instruction,
            "instruction_sha256": digest(args.instruction),
            "route": {"kind": "loopback-http", "endpoint": args.route_endpoint},
        },
    }
    task = task_from(payload, workspace)
    grant = {
        "approval_id": "approval-dsh-readonly-1", "principal": args.approver,
        "task_sha256": task.request_hash,
        "contract_sha256": digest(relay.json_canonical(contract)),
        "issued_at": now.isoformat(),
    }
    bundle = {
        "contract": contract,
        "task": payload,
        "grant": grant,
        "approver_public_key": Path(args.public_key_file).read_text().strip() if args.public_key_file else None,
        "sign_command": (
            "printf '%s' '<canonical grant json>' | "
            "/usr/bin/ssh-keygen -Y sign -f <approver_private_key> -n nexara-p3-approval -"
        ),
        "canonical_grant": relay.json_canonical(grant),
        "note": "This bundle is unsigned. Only the owner may sign it.",
    }
    print(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
