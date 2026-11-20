#!/usr/bin/env python3
"""GitHub <-> Mac read-only MCP relay. No arbitrary command dispatch or model API.

This program is NOT an MCP connector for ordinary ChatGPT. It is an optional,
owner-controlled local relay which polls a GitHub issue and calls an existing
allowlisted local stdio MCP server with fixed empty arguments only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit


REPO, ISSUE, OWNER, OWNER_ID = "Zsx154855/NEXARA-PRIME", 56, "Zsx154855", 170140270
GH = "/opt/homebrew/bin/gh"
PROTOCOL = "NEXARA_READONLY_RELAY_V2"
REQUEST_MARKER = "<!-- NEXARA_READONLY_RELAY_REQUEST_V2 -->"
RECEIPT_MARKER = "<!-- NEXARA_READONLY_RELAY_RECEIPT_V2 -->"
SAFE_TOOLS = frozenset({"nexara_bridge_state", "nexara_evidence_status", "nexara_manifest_summary"})
SAFE_FIELDS = frozenset({"bridge_job_inflight", "receipt_ready", "manifest_present"})
ALLOWED_STATES = (True, False, "unknown")
MAX_REQUEST_AGE_SECONDS = 600
MAX_MCP_LINE = 128 * 1024
MAX_PUBLIC_COMMENT_BYTES = 1000
MAX_GITHUB_BYTES = 8_000_000


class RelayError(Exception):
    pass


class PublishRejected(RelayError):
    """GitHub explicitly rejected this POST before creating a comment."""


class GitHubResourceMissing(RelayError):
    """The GitHub API reports a specific resource is absent."""


def json_canonical(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_utc(s: str) -> dt.datetime:
    if not isinstance(s, str):
        raise RelayError("invalid_time")
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError("naive")
        return d.astimezone(dt.timezone.utc)
    except (ValueError, OverflowError) as e:
        raise RelayError("invalid_time") from e


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate_key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique)


def request_from_comment(comment: dict, owner: str, now: dt.datetime, *, active_only=True) -> dict | None:
    identity = comment.get("user")
    if (not isinstance(identity, dict) or identity.get("login") != owner
            or type(identity.get("id")) is not int or identity["id"] != OWNER_ID):
        return None
    body = comment.get("body", "")
    if not isinstance(body, str) or not body.startswith(REQUEST_MARKER + "\n"):
        return None
    payload = body[len(REQUEST_MARKER):].strip()
    if len(payload) > 1500:
        raise RelayError("oversize_request")
    try:
        req = strict_json(payload)
    except (ValueError, RecursionError) as e:
        raise RelayError("invalid_request_json") from e
    if not isinstance(req, dict) or set(req) != {"protocol", "request_id", "tool", "args", "issued_at", "expires_at"}:
        raise RelayError("invalid_request_schema")
    if req["protocol"] != PROTOCOL or not isinstance(req["tool"], str) or req["tool"] not in SAFE_TOOLS or type(req["args"]) is not dict or req["args"]:
        raise RelayError("request_not_allowlisted")
    rid = req["request_id"]
    if not isinstance(rid, str) or not re.fullmatch(r"[a-z][a-z0-9-]{8,78}", rid):
        raise RelayError("invalid_request_id")
    issued, expires = parse_utc(req["issued_at"]), parse_utc(req["expires_at"])
    if not (dt.timedelta(0) < expires - issued <= dt.timedelta(seconds=MAX_REQUEST_AGE_SECONDS)):
        raise RelayError("invalid_ttl")
    if active_only and not (issued <= now < expires):
        return None
    if type(comment.get("id")) is not int or comment["id"] <= 0:
        raise RelayError("invalid_comment_id")
    req["comment_id"] = comment["id"]
    return req


def redacted_receipt(req: dict, tool_ok: bool, result: Any, mappings: dict[str, str]) -> dict:
    out = {"request_id": req["request_id"], "tool_invoked": bool(tool_ok),
           "bridge_job_inflight": "unknown", "receipt_ready": "unknown",
           "manifest_present": "unknown", "error_code": "NONE" if tool_ok else "TOOL_CALL_FAILED",
           "source": "local_mac_mcp_relay_v01"}
    if tool_ok and isinstance(result, dict):
        for field, path in mappings.items():
            if field not in SAFE_FIELDS or not isinstance(path, str):
                continue
            value: Any = result
            for part in path.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = "unknown"
                    break
                value = value[part]
            if type(value) is bool and not (field == "receipt_ready" and path == "receipt_persisted" and value):
                out[field] = value
    assert all(out[k] in ALLOWED_STATES for k in SAFE_FIELDS)
    return out


def jsonrpc_send(w, msg: dict) -> None:
    w.write((json_canonical(msg) + "\n").encode("utf-8"))
    w.flush()


def jsonrpc_read(stdout, expected: int, timeout: float = 15) -> dict:
    deadline = time.monotonic() + timeout
    pending = bytearray()
    with selectors.DefaultSelector() as sel:
        sel.register(stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            if not sel.select(max(0, deadline - time.monotonic())):
                break
            chunk = os.read(stdout.fileno(), 8192)
            if not chunk:
                raise RelayError("mcp_closed")
            pending.extend(chunk)
            while b"\n" in pending:
                line, _, pending = pending.partition(b"\n")
                if len(line) > MAX_MCP_LINE:
                    raise RelayError("mcp_oversize")
                try:
                    obj = strict_json(line)
                except (ValueError, RecursionError) as e:
                    raise RelayError("mcp_invalid_json") from e
                if isinstance(obj, dict) and type(obj.get("id")) is int and obj["id"] == expected:
                    if obj.get("jsonrpc") != "2.0" or "error" in obj or not isinstance(obj.get("result"), dict):
                        raise RelayError("mcp_rpc_error")
                    return obj["result"]
            if len(pending) > MAX_MCP_LINE:
                raise RelayError("mcp_oversize")
    raise RelayError("mcp_timeout")


def safe_content(result: Any) -> dict:
    if isinstance(result, dict) and result.get("isError"):
        raise RelayError("mcp_tool_error")
    if isinstance(result, dict) and isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    contents = result.get("content", []) if isinstance(result, dict) else []
    for c in contents:
        if isinstance(c, dict) and c.get("type") == "text":
            text = c.get("text")
            if isinstance(text, str) and len(text) <= MAX_MCP_LINE:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
    raise RelayError("mcp_result_unrecognized")


def call_mcp(argv: list[str], tool: str, timeout: int = 15, trace=None, *, require_readonly=False) -> dict:
    if tool not in SAFE_TOOLS:
        raise RelayError("tool_not_allowed")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise RelayError("invalid_local_mcp_command")
    # This command is a *local trusted configuration*, never sourced from GitHub.
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, close_fds=True, shell=False,
                            start_new_session=True, cwd="/", env={})
    try:
        jsonrpc_send(proc.stdin, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                             "clientInfo": {"name": "nexara-readonly-relay", "version": "0.1"}}})
        init = jsonrpc_read(proc.stdout, 1, timeout)
        if init.get("protocolVersion") not in ("2025-11-25", "2025-06-18", "2025-03-26"):
            raise RelayError("mcp_protocol_unverified")
        if trace is not None:
            trace["protocol"] = init["protocolVersion"]
        jsonrpc_send(proc.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        jsonrpc_send(proc.stdin, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = jsonrpc_read(proc.stdout, 2, timeout)
        advertised = next((t for t in listed.get("tools", []) if t.get("name") == tool), None)
        if not advertised:
            raise RelayError("tool_not_advertised")
        if require_readonly and (advertised.get("annotations") or {}).get("readOnlyHint") is not True:
            raise RelayError("tool_readonly_unverified")
        schema = advertised.get("inputSchema", {})
        if not isinstance(schema, dict):
            raise RelayError("tool_schema_invalid")
        if (schema.get("required", []) != [] or schema.get("type") != "object"
                or schema.get("properties") != {} or schema.get("additionalProperties") is not False):
            raise RelayError("tool_schema_not_empty_args")
        jsonrpc_send(proc.stdin, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                      "params": {"name": tool, "arguments": {}}})
        result = safe_content(jsonrpc_read(proc.stdout, 3, timeout))
        if trace is not None:
            trace.update(tool=tool, arguments={}, advertised_schema=schema,
                         tool_call_count=1, response_field_names=sorted(result))
        return result
    finally:
        try:
            proc.stdin.close()
        except (OSError, AttributeError):
            pass
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        if proc.stdout is not None:
            proc.stdout.close()


def atomic_store(path: Path, data: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".relay-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(data, f, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def github_environment():
    identity = pwd.getpwuid(os.getuid())
    return {"HOME": identity.pw_dir, "USER": identity.pw_name, "LOGNAME": identity.pw_name,
            "PATH": "/usr/bin:/bin", "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1", "GH_NO_EXTENSION_UPDATE_NOTIFIER": "1"}


def check_github_call(endpoint, data):
    repo = f"repos/{REPO}"
    issue = f"{repo}/issues/{ISSUE}"
    mailbox = issue + "/comments"
    if data is not None:
        try:
            if endpoint != mailbox or not isinstance(data, dict) or set(data) != {"body"}:
                raise ValueError()
            body = data["body"]
            if (not isinstance(body, str) or len(body.encode()) > MAX_PUBLIC_COMMENT_BYTES
                    or not body.startswith(RECEIPT_MARKER + "\n")):
                raise ValueError()
            receipt = strict_json(body.split("\n", 1)[1])
            rid = receipt["request_id"]
            if not isinstance(rid, str) or not re.fullmatch(r"[a-z][a-z0-9-]{8,78}", rid):
                raise ValueError()
            validate_receipt(receipt, rid)
            if body != receipt_body(receipt):
                raise ValueError()
        except (RelayError, KeyError, TypeError, ValueError, RecursionError) as exc:
            raise RelayError("github_policy_write_rejected") from exc
        return
    if endpoint in ("user", repo, issue) or re.fullmatch(
            re.escape(repo) + r"/issues/comments/[1-9][0-9]{0,19}", endpoint):
        return
    try:
        parsed = urlsplit(endpoint)
        query = parse_qs(parsed.query, strict_parsing=True, max_num_fields=3)
        if (parsed.path == mailbox and not (parsed.scheme or parsed.netloc or parsed.fragment)
                and set(query) in ({"page", "per_page"}, {"page", "per_page", "since"})
                and query["page"] in ([str(i)] for i in range(1, 6))
                and query["per_page"] == ["100"]):
            if "since" in query:
                if len(query["since"]) != 1 or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", query["since"][0]):
                    raise ValueError()
                parse_utc(query["since"][0])
            return
    except (RelayError, ValueError) as exc:
        raise RelayError("github_policy_read_rejected") from exc
    raise RelayError("github_policy_read_rejected")


def bounded_github_output(command, payload, *, timeout=18, limit=MAX_GITHUB_BYTES):
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          cwd="/", env=github_environment(), close_fds=True) as proc:
        try:
            try:
                if payload:
                    proc.stdin.write(payload)
                proc.stdin.close()
            except BrokenPipeError:
                pass
            with selectors.DefaultSelector() as sel:
                sel.register(proc.stdout, selectors.EVENT_READ)
                buf = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not sel.select(remaining):
                        raise RelayError("github_request_timeout")
                    chunk = os.read(proc.stdout.fileno(), 8192)
                    if not chunk:
                        break
                    if len(buf) + len(chunk) > limit:
                        raise RelayError("github_response_limit")
                    buf.extend(chunk)
            code = proc.wait(timeout=max(0, deadline - time.monotonic()))
            return code, buf.decode("utf-8").replace("\r\n", "\n")
        except subprocess.TimeoutExpired as exc:
            raise RelayError("github_request_timeout") from exc
        finally:
            if proc.poll() is None:
                proc.kill()


class GitHubAPI:
    def __init__(self, repo: str, issue: int):
        if repo != REPO or type(issue) is not int or issue != ISSUE:
            raise RelayError("repository_not_pinned")
        self.base = f"repos/{repo}/issues/{issue}/comments"
        actor = self.request("user")
        owner = self.request(f"repos/{repo}").get("owner", {})
        if (actor.get("id") != OWNER_ID or actor.get("login") != OWNER
                or owner.get("id") != OWNER_ID or owner.get("login") != OWNER):
            raise RelayError("github_owner_identity_unverified")
        self.actor_id = OWNER_ID

    def request(self, endpoint, data=None, *, distinguish_missing=False):
        check_github_call(endpoint, data)
        cmd = [GH, "api", "--hostname", "github.com", "--method", "POST" if data is not None else "GET", endpoint]
        if data is not None or distinguish_missing:
            cmd.append("--include")
        if data is not None:
            cmd += ["--input", "-"]
        code, output = bounded_github_output(cmd, json_canonical(data).encode() if data is not None else b"")
        if data is not None or distinguish_missing:
            headers, separator, output = output.partition("\n\n")
            status = re.match(r"^HTTP/\S+ ([1-5][0-9]{2})(?:[ \n]|$)", headers)
            if distinguish_missing and separator and status and status[1] in ("404", "410"):
                raise GitHubResourceMissing("github_resource_missing")
            if data is not None and separator and status and status[1] in ("401", "403", "429"):
                raise PublishRejected("github_post_rejected_" + status[1])
            if not separator or not status or status[1] != ("201" if data is not None else "200"):
                raise RelayError("github_response_unverified")
        if code:
            raise RelayError("github_request_failed")
        return strict_json(output)

    def comments(self):
        out = []
        for page in range(1, 6):
            chunk = self.request(f"{self.base}?per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise RelayError("github_invalid_comments")
            out.extend(chunk)
            if len(chunk) < 100:
                return out
        raise RelayError("github_scan_incomplete")

    def post(self, body):
        if len(body.encode()) > MAX_PUBLIC_COMMENT_BYTES:
            raise RelayError("public_receipt_too_large")
        return self.request(self.base, {"body": body})


def receipt_body(receipt: dict) -> str:
    return RECEIPT_MARKER + "\n" + json_canonical(receipt)


def existing_receipts(comments: list[dict], rid: str) -> list[dict]:
    found = []
    for c in comments:
        body = c.get("body", "")
        if not isinstance(body, str) or not body.startswith(RECEIPT_MARKER + "\n"):
            continue
        try:
            p = json.loads(body[len(RECEIPT_MARKER):].strip())
            if isinstance(p, dict) and p.get("request_id") == rid:
                found.append(c)
        except ValueError:
            continue
    return found


def validate_receipt(receipt, rid):
    keys = SAFE_FIELDS | {"request_id", "tool_invoked", "error_code", "source"}
    if (not isinstance(receipt, dict) or set(receipt) != keys or receipt["request_id"] != rid
            or receipt["tool_invoked"] is not True or receipt["source"] != "local_mac_mcp_relay_v01"
            or receipt["error_code"] != "NONE"
            or not all(type(receipt[k]) is bool or receipt[k] == "unknown" for k in SAFE_FIELDS)):
        raise RelayError("receipt_not_allowlisted")


def state_read(path):
    if path.is_symlink():
        raise RelayError("state_symlink")
    if not path.exists():
        return {"jobs": {}}
    return private_json(path, 4_000_000)


def process_once(api: GitHubAPI, owner: str, statepath: Path, mcp_argv: list[str], mappings: dict) -> list[str]:
    comments = api.comments()
    now = dt.datetime.now(dt.timezone.utc)
    valid = []
    counts = {}
    for c in comments:
        try:
            req = request_from_comment(c, owner, now, active_only=False)
            if req:
                rid = req["request_id"]
                counts[rid] = counts.get(rid, 0) + 1
                if parse_utc(req["issued_at"]) <= now < parse_utc(req["expires_at"]):
                    valid.append(req)
        except RelayError:
            pass
    state = state_read(statepath)
    if not isinstance(state, dict) or set(state) != {"jobs"} or not isinstance(state["jobs"], dict) or len(state["jobs"]) > 5000 or any(not isinstance(v, dict) for v in state["jobs"].values()):
        raise RelayError("journal_invalid_or_full")
    statuses = []
    for req in sorted(valid, key=lambda q: q["comment_id"]):
        rid = req["request_id"]
        if counts[rid] != 1:
            statuses.append("DUPLICATE_REQUEST_REJECTED")
            continue
        job = state["jobs"].get(rid)
        if job and job.get("phase") == "POSTED":
            statuses.append("RECEIPT_ALREADY_POSTED")
            continue
        prior = existing_receipts(comments, rid)
        if prior:
            statuses.append("REMOTE_RECEIPT_PRESENT_QUARANTINED")
            continue
        if job and job.get("source_comment_id") != req["comment_id"]:
            statuses.append("REQUEST_ID_REUSED_REJECTED")
            continue
        if job and job.get("phase") in ("INFLIGHT", "POST_UNCERTAIN"):
            statuses.append(job["phase"] + "_QUARANTINED")
            continue
        if os.path.lexists(statepath.parent / "STOP"):
            return statuses + ["STOPPED_BY_OPERATOR"]
        if dt.datetime.now(dt.timezone.utc) >= parse_utc(req["expires_at"]):
            return statuses + ["REQUEST_EXPIRED"]
        if not job:
            state["jobs"][rid] = job = {"phase": "INFLIGHT", "source_comment_id": req["comment_id"], "request": req}
            atomic_store(statepath, state)
            try:
                result = call_mcp(mcp_argv, req["tool"])
                receipt = redacted_receipt(req, True, result, mappings.get(req["tool"], {}))
                validate_receipt(receipt, rid)
            except (RelayError, OSError, ValueError, subprocess.SubprocessError):
                return statuses + ["INFLIGHT_QUARANTINED"]
            job.update(phase="READY", receipt=receipt)
            atomic_store(statepath, state)
        elif job.get("phase") != "READY" or job.get("request") != req:
            statuses.append("UNKNOWN_OR_CHANGED_PHASE_QUARANTINED")
            continue
        validate_receipt(job.get("receipt"), rid)
        if os.path.lexists(statepath.parent / "STOP"):
            return statuses + ["STOPPED_BY_OPERATOR"]
        fresh = api.comments()
        current_time = dt.datetime.now(dt.timezone.utc)
        if current_time >= parse_utc(req["expires_at"]):
            return statuses + ["REQUEST_EXPIRED"]
        same = []
        for c in fresh:
            try:
                candidate = request_from_comment(c, owner, current_time, active_only=False)
                if candidate and candidate["request_id"] == rid:
                    same.append(candidate)
            except RelayError:
                pass
        if same != [req] or existing_receipts(fresh, rid):
            return statuses + ["REQUEST_CHANGED_OR_RECEIPT_PRESENT"]
        body = receipt_body(job["receipt"])
        job["phase"] = "POST_UNCERTAIN"
        atomic_store(statepath, state)
        if os.path.lexists(statepath.parent / "STOP"):
            return statuses + ["STOPPED_BY_OPERATOR"]
        if dt.datetime.now(dt.timezone.utc) >= parse_utc(req["expires_at"]):
            return statuses + ["REQUEST_EXPIRED_BEFORE_POST"]
        try:
            posted = api.post(body)
            ident = posted.get("id") if isinstance(posted, dict) else None
            if type(ident) is not int or ident <= 0:
                raise RelayError("post_id_unverified")
            rows = existing_receipts(api.comments(), rid)
            if (len(rows) != 1 or rows[0].get("id") != ident or rows[0].get("body") != body
                    or (rows[0].get("user") or {}).get("id") != api.actor_id):
                raise RelayError("post_readback_unverified")
        except Exception:
            return statuses + ["POST_UNCERTAIN_QUARANTINED"]
        job.update(phase="POSTED", receipt_comment_id=ident)
        atomic_store(statepath, state)
        return statuses + ["POSTED"]
    return statuses or ["NO_ELIGIBLE_V2_REQUEST"]


def private_json(path, limit=100_000):
    parent = path.parent
    ps = parent.stat()
    if (parent.resolve() != parent.absolute() or ps.st_uid != os.getuid()
            or stat.S_IMODE(ps.st_mode) != 0o700):
        raise RelayError("private_directory_unverified")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
                or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > limit):
            raise RelayError("private_file_unverified")
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise RelayError("private_file_limit")
    return strict_json(raw)


def load_config(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RelayError("config_missing_or_symlink")
    if path.stat().st_mode & 0o077:
        raise RelayError("config_permissions_too_broad")
    d = private_json(path)
    if not isinstance(d, dict) or set(d) != {"repo", "issue", "owner", "mcp_argv", "field_paths", "poll_seconds"}:
        raise RelayError("invalid_config_schema")
    if ((d["repo"], d["issue"], d["owner"]) != (REPO, ISSUE, OWNER) or type(d["issue"]) is not int
            or not isinstance(d["mcp_argv"], list) or not d["mcp_argv"]
            or not all(isinstance(a, str) and a for a in d["mcp_argv"]) or not Path(d["mcp_argv"][0]).is_absolute()):
        raise RelayError("untrusted_local_config")
    if type(d["poll_seconds"]) is not int or not 30 <= d["poll_seconds"] <= 3600:
        raise RelayError("invalid_poll_interval")
    if not isinstance(d["field_paths"], dict):
        raise RelayError("invalid_field_paths")
    if set(d["field_paths"]) - SAFE_TOOLS:
        raise RelayError("invalid_field_paths_tool")
    return d


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true", help="One poll; default unless --serve")
    parser.add_argument("--serve", action="store_true", help="Reserved pending the unattended security review")
    parser.add_argument("--inspect", action="store_true", help="Read and validate the mailbox without claiming")
    parser.add_argument("--dry-run", action="store_true", help="Inspect config only; no MCP or GitHub actions")
    args = parser.parse_args()
    if args.once and args.serve:
        parser.error("choose one execution mode")
    try:
        cfg = load_config(args.config)
        if args.dry_run:
            print("CONFIG_VALIDATED")
            return 0
        if args.serve:
            raise RelayError("PERSISTENCE_SECURITY_NOT_VERIFIED")
        if os.path.lexists(args.config.parent / "STOP"):
            raise RelayError("STOPPED_BY_OPERATOR")
        if args.inspect:
            api = GitHubAPI(cfg["repo"], cfg["issue"])
            rows = api.comments()
            now = dt.datetime.now(dt.timezone.utc)
            candidates = []
            for c in rows:
                try:
                    if request_from_comment(c, cfg["owner"], now):
                        candidates.append(c["id"])
                except RelayError:
                    pass
            print(json_canonical({"owner_verified":True,"comments_scanned":len(rows),"eligible_shape_and_time_count":len(candidates)}))
            return 0
        statepath = args.config.parent / "state.json"
        lockpath = args.config.parent / "relay.lock"
        fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd) as lock:
            st = os.fstat(lock.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600:
                raise RelayError("lock_unverified")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.path.lexists(args.config.parent / "durable.sqlite3"):
                raise RelayError("durable_ledger_present_use_durable")
            api = GitHubAPI(cfg["repo"], cfg["issue"])
            statuses = process_once(api, cfg["owner"], statepath, cfg["mcp_argv"], cfg["field_paths"])
            for status in statuses:
                print(status, flush=True)
        return 0 if "POSTED" in statuses or "RECEIPT_ALREADY_POSTED" in statuses else 3
    except (RelayError, OSError, ValueError, BlockingIOError, json.JSONDecodeError) as e:
        print("RELAY_BLOCKED=" + (str(e) if isinstance(e, RelayError) else type(e).__name__))
        return 2


if __name__ == "__main__":
    sys.exit(main())
