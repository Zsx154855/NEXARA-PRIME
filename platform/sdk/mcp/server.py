"""NEXARA PRIME MCP Server — governed tool exposure via Model Context Protocol.

Exposes NEXARA Runtime Truth API as MCP tools. All tools are governed by
NEXARA Policy/Approval — MCP does NOT bypass security controls.
"""
from __future__ import annotations

import json
import sys
from typing import Any


class NexaraMCPServer:
    """Minimal MCP server exposing NEXARA Runtime Truth as governed tools.

    Protocol: reads JSON-RPC from stdin, writes to stdout.
    Tools are read-only by default — mutation requires explicit approval.
    """

    TOOLS = {
        "nexara.health": {
            "description": "Check NEXARA Runtime health and connection status",
            "inputSchema": {"type": "object", "properties": {}},
        },
        "nexara.list_missions": {
            "description": "List all NEXARA missions with their current state",
            "inputSchema": {"type": "object", "properties": {}},
        },
        "nexara.get_mission": {
            "description": "Get mission details by ID",
            "inputSchema": {
                "type": "object",
                "properties": {"mission_id": {"type": "string"}},
                "required": ["mission_id"],
            },
        },
        "nexara.create_mission": {
            "description": "Create a new mission (governed: requires approval per policy)",
            "inputSchema": {
                "type": "object",
                "properties": {"objective": {"type": "string"}},
                "required": ["objective"],
            },
        },
        "nexara.runtime_overview": {
            "description": "Get Runtime Truth system overview (mock/live status, security, capability inventory)",
            "inputSchema": {"type": "object", "properties": {}},
        },
        "nexara.evidence_scan": {
            "description": "Scan evidence ledger for a mission",
            "inputSchema": {
                "type": "object",
                "properties": {"mission_id": {"type": "string"}},
            },
        },
    }

    def __init__(self, api_base: str = "http://127.0.0.1:8765"):
        self.api_base = api_base
        self._tools = dict(self.TOOLS)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        req_id = request.get("id")

        if method == "tools/list":
            return self._response(req_id, {"tools": list(self._tools.values())})

        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                result = self._call_tool(tool_name, args)
                return self._response(req_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
            except Exception as e:
                return self._response(req_id, {"content": [{"type": "text", "text": f"Error: {e}"}]}, is_error=True)

        return self._response(req_id, {}, is_error=True)

    def _call_tool(self, name: str, args: dict[str, Any]) -> Any:
        import urllib.request

        if name == "nexara.health":
            return json.loads(urllib.request.urlopen(f"{self.api_base}/health").read())

        if name == "nexara.list_missions":
            return json.loads(urllib.request.urlopen(f"{self.api_base}/api/missions").read())

        if name == "nexara.get_mission":
            mid = args.get("mission_id", "")
            return json.loads(urllib.request.urlopen(f"{self.api_base}/api/missions/{mid}").read())

        if name == "nexara.runtime_overview":
            return json.loads(urllib.request.urlopen(f"{self.api_base}/api/runtime/overview").read())

        if name == "nexara.create_mission":
            body = json.dumps({"objective": args["objective"]}).encode()
            req = urllib.request.Request(f"{self.api_base}/api/missions", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            return json.loads(urllib.request.urlopen(req).read())

        if name == "nexara.evidence_scan":
            mid = args.get("mission_id", "")
            ov = json.loads(urllib.request.urlopen(f"{self.api_base}/api/runtime/overview").read())
            return [e for e in ov.get("evidence", []) if mid in str(e)]

        raise ValueError(f"Unknown tool: {name}")

    def _response(self, req_id: Any, result: dict, is_error: bool = False) -> dict:
        key = "error" if is_error else "result"
        return {"jsonrpc": "2.0", key: result, "id": req_id}

    def run(self) -> None:
        """Read JSON-RPC from stdin, write responses to stdout."""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self.handle(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                continue


if __name__ == "__main__":
    NexaraMCPServer().run()
