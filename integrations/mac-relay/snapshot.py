"""Generate or validate a short-lived, minimal MCP summary in private storage."""

import argparse
import datetime as dt
import os
from pathlib import Path
import stat

import relay


NAME = "mcp-summary.json"
MAX_BYTES = 2048
MAX_AGE = dt.timedelta(seconds=120)
FIELDS = {
    "nexara_bridge_state": ("known_job_inflight", "receipt_persisted"),
    "nexara_evidence_status": ("manifest_exists",),
    "nexara_manifest_summary": ("manifest_present",),
}


def validated_tools(tools):
    if not isinstance(tools, dict) or not tools or not set(tools) <= set(FIELDS):
        raise relay.RelayError("snapshot_tool_invalid")
    for tool, result in tools.items():
        if not isinstance(result, dict) or not set(result) <= {"status", *FIELDS[tool]}:
            raise relay.RelayError("snapshot_field_invalid")
        status = result.get("status")
        if status == "PASS":
            if not all(type(result.get(name)) is bool for name in FIELDS[tool]):
                raise relay.RelayError("snapshot_boolean_missing")
        elif status != "NOT_VERIFIED" or tool != "nexara_manifest_summary":
            raise relay.RelayError("snapshot_status_invalid")
        if any(type(value) is not bool for key, value in result.items() if key != "status"):
            raise relay.RelayError("snapshot_field_invalid")
    return tools


def create(results, now):
    tools = {}
    for tool, result in results.items():
        if tool not in FIELDS or not isinstance(result, dict):
            raise relay.RelayError("snapshot_tool_invalid")
        tools[tool] = {"status": result.get("status")}
        for name in FIELDS[tool]:
            if type(result.get(name)) is bool:
                tools[tool][name] = result[name]
    return {"version": 1, "generated_at": now.isoformat(timespec="seconds"),
            "tools": validated_tools(tools)}


def read(folder, producer_uid, now):
    if not folder.is_absolute() or folder.anchor != "/" or ".." in folder.parts:
        raise relay.RelayError("snapshot_path_unverified")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in folder.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != producer_uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise relay.RelayError("snapshot_directory_unverified")
        file_fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != producer_uid or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_BYTES):
                raise relay.RelayError("snapshot_file_unverified")
            raw = handle.read(MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > MAX_BYTES:
        raise relay.RelayError("snapshot_too_large")
    row = relay.strict_json(raw)
    if (not isinstance(row, dict) or set(row) != {"version", "generated_at", "tools"}
            or type(row["version"]) is not int or row["version"] != 1):
        raise relay.RelayError("snapshot_version_invalid")
    age = now - relay.parse_utc(row["generated_at"])
    if not dt.timedelta(0) <= age <= MAX_AGE:
        raise relay.RelayError("snapshot_not_fresh")
    return validated_tools(row["tools"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = args.config.absolute()
        cfg = relay.load_config(config)
        now = dt.datetime.now(dt.timezone.utc)
        results = {tool: relay.call_mcp(cfg["mcp_argv"], tool, require_readonly=True) for tool in sorted(FIELDS)}
        row = create(results, now)
        validated_tools(row["tools"])
        if dt.datetime.now(dt.timezone.utc) - now > MAX_AGE:
            raise relay.RelayError("snapshot_generation_timed_out")
        relay.atomic_store(config.parent / NAME, row)
        read(config.parent, os.getuid(), dt.datetime.now(dt.timezone.utc))
    except (relay.RelayError, OSError, ValueError, RecursionError):
        print("SNAPSHOT_BLOCKED")
        return 2
    print("PRIVATE_SNAPSHOT_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
