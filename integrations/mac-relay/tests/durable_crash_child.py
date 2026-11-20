"""Exit without finally blocks at a controlled boundary in a disposable ledger."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import durable
import relay
from test_durable import Mailbox, NOW, request


folder = Path(sys.argv[1])
boundary = sys.argv[2]


class CrashMailbox(Mailbox):
    def post(self, body):
        posted = super().post(body)
        with (folder / "accepted.json").open("w") as file:
            json.dump(posted, file)
            file.flush()
            os.fsync(file.fileno())
        os._exit(73)


class CrashWorker(durable.Controller):
    def publish(self, row):
        if boundary == "staged":
            os._exit(73)
        return super().publish(row)


def invoke(*_):
    if boundary == "mcp":
        os._exit(73)
    return {"status": "PASS"}


cfg = dict(owner=relay.OWNER, mcp_argv=["/fixture"], field_paths={})
try:
    with CrashWorker(folder, CrashMailbox([request()]), cfg, now=lambda: NOW, invoke=invoke) as worker:
        worker.tick()
except BlockingIOError:
    raise SystemExit(75)
