"""Exercise the broker socket with the real Mac MCP and an offline GitHub fixture."""

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay
from p2_broker import broker_call
from test_p2_broker import child_fixture


def main(config):
    cfg = relay.load_config(config)
    bridge = Path.home() / ".nexara_mac_bridge_v04/state.json"
    before = hashlib.sha256(bridge.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="p2-mcp-", dir="/tmp") as directory:
        private = Path(directory).resolve()
        endpoint = private / "gh.sock"
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        child = context.Process(target=child_fixture, args=(endpoint, private, ready))
        child.start()
        try:
            assert ready.wait(4)
            source, = broker_call(endpoint, {"op": "read_requests"}, broker_uid=os.geteuid())["requests"]
            assert source["tool"] == "nexara_bridge_state" and source["args"] == {}
            trace = {}
            result = relay.call_mcp(cfg["mcp_argv"], source["tool"], trace=trace, require_readonly=True)
            assert result["status"] == "PASS" and trace["tool_call_count"] == 1
            receipt = relay.redacted_receipt(source, True, result, cfg["field_paths"][source["tool"]])
            response = broker_call(endpoint, {"op": "publish_receipt", "source_id": source["comment_id"],
                                               "source_sha256": source["source_sha256"], "receipt": receipt},
                                   broker_uid=os.geteuid())
            assert response == {"status": "published", "receipt_id": 902}
            child.join(4)
            assert child.exitcode == 0
        finally:
            if child.is_alive():
                child.terminate()
                child.join()
    assert hashlib.sha256(bridge.read_bytes()).hexdigest() == before
    print(json.dumps({"status": "PASS", "separate_broker_process": True, "macos_peer_uid_checked": True,
                      "real_mcp_calls": 1, "receipt_fields": len(receipt), "fixture_readback": True,
                      "github_fixture": True, "cross_uid": False, "bridge_unchanged": True}))


if __name__ == "__main__":
    main(Path(sys.argv[1]).absolute())
