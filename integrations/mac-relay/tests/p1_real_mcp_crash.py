"""Run the installed MCP once, then abruptly terminate before staging its result."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import durable
import relay
from test_durable import Mailbox, NOW, RID, request


def child(folder, config):
    cfg = relay.load_config(config)
    mailbox = Mailbox([request()])

    def invoke(argv, tool):
        result = relay.call_mcp(argv, tool, require_readonly=True)
        assert result["status"] == "PASS" and type(result["known_job_inflight"]) is bool
        relay.atomic_store(folder / "mcp-returned.json", {"completed_calls": 1})
        os._exit(73)

    with durable.Controller(folder, mailbox, cfg, now=lambda: NOW, invoke=invoke) as controller:
        controller.tick()
    raise SystemExit(2)


def verify(config):
    cfg = relay.load_config(config)
    state = Path.home() / ".nexara_mac_bridge_v04/state.json"
    before = hashlib.sha256(state.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory).resolve()
        result = subprocess.run([sys.executable, "-B", __file__, str(config), str(folder)],
                                capture_output=True, timeout=55)
        assert result.returncode == 73, "MCP crash point not reached"
        assert relay.private_json(folder / "mcp-returned.json") == {"completed_calls": 1}

        def forbidden(*_):
            raise AssertionError("unknown-outcome MCP was invoked again")

        mailbox = Mailbox([request()])
        with durable.Controller(folder, mailbox, cfg, now=lambda: NOW, invoke=forbidden) as controller:
            task = controller.job(RID)
            assert task["phase"] == "QUARANTINED" and task["raw_result"] is None
            assert controller.tick() == "IDLE" and mailbox.posts == 0
    assert hashlib.sha256(state.read_bytes()).hexdigest() == before
    print(json.dumps({"real_mcp_calls_before_exit": 1, "injected_exit_code": 73,
                      "reopened_phase": "QUARANTINED", "replayed_calls": 0,
                      "github_fixture_posts": 0, "old_bridge_state_unchanged": True}))


if __name__ == "__main__":
    config = Path(sys.argv[1]).absolute()
    if len(sys.argv) == 3:
        child(Path(sys.argv[2]), config)
    else:
        verify(config)
