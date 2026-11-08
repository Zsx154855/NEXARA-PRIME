#!/usr/bin/env python3
"""Fake documented headless CLI for isolated contract tests, NOT real Agents."""
import json
import os
import pathlib
import sys

state_file = pathlib.Path(os.environ["AEP_TEST_STATE"])
s = json.loads(state_file.read_text()) if state_file.exists() else {"calls": [], "unique_sends": {}, "send_attempts": 0}
args = sys.argv[1:]
verb = args[0]
s["calls"].append(args)
code = 0
if verb == "run":
    s["send_attempts"] += 1
    send_id = args[args.index("--send-id") + 1]
    target = args[args.index("--task") + 1]
    objective = sys.stdin.read()
    if not objective:
        code, result = 2, {"ok": False, "error": "missing stdin", "exitCode": 2}
    elif os.environ.get("AEP_SEND_UNREACHABLE") == "1":
        code, result = 5, {"ok": False, "error": "offline", "exitCode": 5}
    else:
        if send_id not in s["unique_sends"]:
            s["unique_sends"][send_id] = {"ok": True, "threadId": target,
                                          "messageId": f"msg-{len(s['unique_sends']) + 1}",
                                          "sendId": send_id, "since": 1000, "at": 1001, "text": objective}
        result = s["unique_sends"][send_id].copy()
        if os.environ.get("AEP_STEERED") == "1":
            result["steered"] = True
        if os.environ.get("AEP_QUEUED") == "1":
            result["queued"] = True
        if os.environ.get("AEP_MISMATCH") == "1":
            result["threadId"] = "wrong-task"
        if os.environ.get("AEP_ANCHOR_STALE") == "1":
            result["since"] = 2000
elif verb == "wait":
    status = os.environ.get("AEP_WAIT_STATUS", "completed")
    actors = ["research", "engineer", "auditor"] if os.environ.get("AEP_TEAM", "1") == "1" else ["research"]
    nodes = [{"botId": b, "id": f"node-{b}", "status": "completed"} for b in actors]
    if os.environ.get("AEP_NODE_RUNNING") == "1":
        nodes[-1]["status"] = "running"
    code = {"completed": 0, "failed": 1, "needs-input": 3, "timed-out": 4, "offline": 5}.get(status, 1)
    job = {"threadId": "thread-fixed", "nodes": nodes, "counts": {"failed": 0}, "since": 1000}
    if os.environ.get("AEP_WRONG_JOB") == "1":
        job["threadId"] = "old-thread"
    if os.environ.get("AEP_STALE_JOB") == "1":
        job["since"] = 900
    if os.environ.get("AEP_FAILED_COUNTS") == "1":
        job["counts"]["failed"] = 1
    result = {"ok": code == 0, "state": status,
              "status": "settled" if status in {"completed", "failed"} else status,
              "taskId": "thread-fixed", "job": job, "exitCode": code}
    if status == "failed":
        result["job"]["nodes"].append({"id": "node-failed", "botId": "x", "status": "failed"})
else:
    code, result = 2, {"ok": False, "error": "bad command", "exitCode": 2}
state_file.write_text(json.dumps(s))
print(json.dumps(result))
sys.exit(code)
