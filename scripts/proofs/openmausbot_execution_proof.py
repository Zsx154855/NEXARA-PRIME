"""Explicit, finite NEXARA/OpenMausBot laboratory runner. No daemon."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nexara_prime.integrations.openmausbot_execution import ExecutionProof, OMBCLI, ProofError, TaskLedger


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NEXARA x OpenMausBot isolated execution proof")
    parser.add_argument("action", choices=("submit", "resume", "inspect"))
    parser.add_argument("--db", required=True, help="SQLite file in isolated lab directory")
    parser.add_argument("--binary", default="openmausbot", help="OpenMausBot CLI executable")
    parser.add_argument("--url", default="http://127.0.0.1:8799")
    parser.add_argument("--token-file")
    parser.add_argument("--proposal-json", help="JSON file containing an existing cognitive proposal")
    parser.add_argument("--bot-id", help="Existing OpenMausBot lead bot ID")
    parser.add_argument("--thread-id", help="Dedicated existing OpenMausBot task thread ID")
    parser.add_argument("--mission-id", help="NEXARA mission / cognitive proposal ID")
    args = parser.parse_args(argv)
    ledger = TaskLedger(Path(args.db))
    try:
        cli = OMBCLI(executable=args.binary, url=args.url, token_file=args.token_file)
        proof = ExecutionProof(ledger, cli)
        if args.action == "submit":
            if not args.proposal_json or not args.bot_id or not args.thread_id:
                parser.error("submit requires --proposal-json, --bot-id, --thread-id")
            proposal = json.loads(Path(args.proposal_json).read_text())
            result = proof.submit_proposal(proposal, args.bot_id, args.thread_id)
        else:
            if not args.mission_id:
                parser.error("resume / inspect require --mission-id")
            result = proof.reconcile(args.mission_id) if args.action == "resume" else ledger.get(args.mission_id)
            if result is None:
                raise ProofError("mission_not_found")
        public = {key: result[key] for key in ("id", "status", "message_id")}
        if result["status"] in {"REPORTED", "EXECUTION_FAILED"}:
            public["team_report"] = proof.team_evidence(result["id"])
        print(json.dumps({"ok": True, "mission": public}, ensure_ascii=False))
        return 0
    except (ProofError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
