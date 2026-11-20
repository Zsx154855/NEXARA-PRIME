"""Credential-side Issue #56 broker. The worker interface is only broker_call."""
from __future__ import annotations

from contextlib import closing, contextmanager
import ctypes
from collections import Counter
import datetime as dt
import errno
import hashlib
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import sys
import time
from typing import Protocol

from durable import ISSUE_API, private_fd
import relay


REPO_API = f"repos/{relay.REPO}"
COMMENTS_API = ISSUE_API + "/comments"
ISSUE_URL = "https://api.github.com/" + ISSUE_API
MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 64 * 1024
MAX_TRANSPORT_BYTES = 512 * 1024
BROKER_TIMEOUT = 20


class Transport(Protocol):
    def request(self, method: str, path: str, payload: dict | None, *,
                deadline: float, max_bytes: int) -> object:
        """Use github.com only, enforce the monotonic deadline and byte cap, and never retry POST."""


class BrokerError(relay.RelayError):
    """An error code safe to return to a worker."""


def _peer_uid(connection: socket.socket) -> int:
    # Python does not expose getpeereid on every macOS build.
    if sys.platform != "darwin":
        raise BrokerError("peer_denied")
    getpeereid = ctypes.CDLL(None, use_errno=True).getpeereid
    getpeereid.argtypes = (ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint))
    getpeereid.restype = ctypes.c_int
    uid, gid = ctypes.c_uint(), ctypes.c_uint()
    if getpeereid(connection.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
        raise BrokerError("peer_denied")
    return uid.value


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _receive(connection: socket.socket, limit: int, deadline: float) -> dict:
    raw = bytearray()
    while len(raw) <= limit:
        connection.settimeout(_remaining(deadline))
        data = connection.recv(min(4096, limit + 1 - len(raw)))
        if not data:
            try:
                value = relay.strict_json(raw.decode("utf-8"))
            except (ValueError, RecursionError) as exc:
                raise BrokerError("invalid_request") from exc
            if type(value) is dict:
                return value
            break
        raw.extend(data)
    raise BrokerError("invalid_request")


def _encoded(value: object, limit: int) -> bytes:
    raw = relay.json_canonical(value).encode()
    if len(raw) > limit:
        raise BrokerError("size_limit")
    return raw


def broker_call(socket_path: Path, request: dict, *, broker_uid: int,
                timeout: float = BROKER_TIMEOUT + 1) -> dict:
    """Worker-side socket request. A disconnected publication must remain ambiguous."""
    deadline = time.monotonic() + timeout
    payload = _encoded(request, MAX_REQUEST_BYTES)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(_remaining(deadline))
        connection.connect(str(socket_path))
        if _peer_uid(connection) != broker_uid:
            raise BrokerError("peer_denied")
        connection.settimeout(_remaining(deadline))
        try:
            connection.sendall(payload)
            connection.shutdown(socket.SHUT_WR)
        except OSError as exc:
            # The broker may send a denial and close before it reads the request.
            if exc.errno not in (errno.ENOTCONN, errno.EPIPE, errno.ECONNRESET):
                raise
        return _receive(connection, MAX_RESPONSE_BYTES, deadline)


def _trusted_directory(path: Path, modes: tuple[int, ...]) -> os.stat_result:
    info = path.lstat()
    uid = os.geteuid()
    if (path != path.resolve() or not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) not in modes):
        raise BrokerError("broker_directory_unverified")
    for ancestor in path.parents:
        parent = ancestor.lstat()
        writable = parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        root_sticky = parent.st_uid == 0 and parent.st_mode & stat.S_ISVTX
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid not in (0, uid) or (writable and not root_sticky):
            raise BrokerError("broker_directory_unverified")
    return info


def _identity(row: dict) -> tuple:
    actor = row.get("user")
    if not isinstance(actor, dict) or type(actor.get("id")) is not int:
        return ()
    return actor.get("login"), actor["id"]


def _comment_id(row: dict) -> int | None:
    ident = row.get("id")
    if type(ident) is int and 0 < ident <= 2**63 - 1 and row.get("issue_url") == ISSUE_URL:
        return ident
    return None


class GitHubBroker:
    """Serialize admission and publishing in the credential-holding process."""

    def __init__(self, socket_path: Path, state_dir: Path, transport: Transport, *,
                 worker_uid: int, publisher: tuple[str, int], now=None, timeout: float = BROKER_TIMEOUT):
        self.socket_path = socket_path
        self.state_dir = state_dir
        self.transport = transport
        self.worker_uid = worker_uid
        self.publisher = publisher
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.timeout = timeout

    def __enter__(self):
        _trusted_directory(self.state_dir, (0o700,))
        directory = _trusted_directory(self.socket_path.parent, (0o700, 0o710))
        if (self.worker_uid != os.geteuid() and stat.S_IMODE(directory.st_mode) != 0o710
                or self.socket_path.name != "gh.sock"):
            raise BrokerError("broker_socket_unverified")
        with self._database() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                  id INTEGER PRIMARY KEY, rid TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL,
                  attempted INTEGER NOT NULL DEFAULT 0
                )
            """)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        bound = False
        try:
            self.listener.bind(str(self.socket_path))
            bound = True
            if stat.S_IMODE(directory.st_mode) == 0o710:
                os.chown(self.socket_path, -1, directory.st_gid)
                self.socket_path.chmod(0o660)
            else:
                self.socket_path.chmod(0o600)
            self.listener.listen(8)
        except BaseException:
            self.listener.close()
            if bound:
                self.socket_path.unlink()
            raise
        return self

    def __exit__(self, *_):
        self.listener.close()
        self.socket_path.unlink()

    @contextmanager
    def _database(self):
        path = self.state_dir / "broker.sqlite3"
        with private_fd(path):
            sidecar = path.with_name(path.name + "-journal")
            if os.path.lexists(sidecar):
                with private_fd(sidecar):
                    pass
            with closing(sqlite3.connect(path, timeout=.1)) as db, db:
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA fullfsync=ON")
                db.execute("PRAGMA max_page_count=4096")
                yield db

    def serve_one(self) -> None:
        connection, _ = self.listener.accept()
        with connection:
            deadline = time.monotonic() + self.timeout
            try:
                if _peer_uid(connection) != self.worker_uid:
                    raise BrokerError("peer_denied")
                result = self._dispatch(_receive(connection, MAX_REQUEST_BYTES, deadline), deadline)
                payload = _encoded(result, MAX_RESPONSE_BYTES)
            except BrokerError as exc:
                payload = _encoded({"error": str(exc)}, MAX_RESPONSE_BYTES)
            except TimeoutError:
                payload = b'{"error":"deadline"}'
            except (relay.RelayError, OSError, sqlite3.Error, ValueError, RecursionError):
                payload = b'{"error":"upstream_unverified"}'
            try:
                # Bound the error reply too, including when the request deadline elapsed.
                connection.settimeout(min(.1, max(.001, deadline - time.monotonic())))
                connection.sendall(payload)
            except OSError:
                pass

    def _request(self, deadline: float, path: str, payload: dict | None = None):
        _remaining(deadline)
        if payload is None and path != ISSUE_API and not (
                re.fullmatch(re.escape(COMMENTS_API) + r"\?per_page=100&page=[1-5]", path)
                or re.fullmatch(re.escape(REPO_API) + r"/issues/comments/[1-9][0-9]{0,18}", path)):
            raise BrokerError("upstream_unverified")
        relay.check_github_call(path, payload)
        method = "POST" if payload is not None else "GET"
        try:
            result = self.transport.request(method, path, payload, deadline=deadline,
                                            max_bytes=MAX_TRANSPORT_BYTES)
        except Exception as exc:
            raise BrokerError("upstream_unverified") from exc
        _remaining(deadline)
        _encoded(result, MAX_TRANSPORT_BYTES)
        return result

    def _scan(self, deadline: float) -> list[dict]:
        issue = self._request(deadline, ISSUE_API)
        if (not isinstance(issue, dict) or type(issue.get("number")) is not int
                or issue["number"] != relay.ISSUE or issue.get("state") != "open"
                or issue.get("repository_url") != "https://api.github.com/" + REPO_API):
            raise BrokerError("issue_unverified")
        rows = []
        for page in range(1, 6):
            chunk = self._request(deadline, f"{COMMENTS_API}?per_page=100&page={page}")
            if (not isinstance(chunk, list) or len(chunk) > 100
                    or any(not isinstance(row, dict) or _comment_id(row) is None for row in chunk)):
                raise BrokerError("upstream_unverified")
            rows.extend(chunk)
            if len(chunk) < 100:
                return rows
        raise BrokerError("scan_incomplete")

    def _source(self, row: object, *, active_only=True) -> dict | None:
        if not isinstance(row, dict) or _comment_id(row) is None:
            return None
        try:
            req = relay.request_from_comment(row, relay.OWNER, self.now(), active_only=active_only)
            if req is None:
                return None
            created = relay.parse_utc(row.get("created_at"))
            updated = relay.parse_utc(row.get("updated_at"))
            if created != updated or not relay.parse_utc(req["issued_at"]) <= created < relay.parse_utc(req["expires_at"]):
                return None
            return {**req, "source_sha256": hashlib.sha256(row["body"].encode()).hexdigest()}
        except (relay.RelayError, UnicodeError):
            return None

    def _dispatch(self, request: dict, deadline: float) -> dict:
        if request == {"op": "read_requests"}:
            return self._read(deadline)
        if set(request) == {"op", "source_id", "source_sha256", "receipt"} and request["op"] == "publish_receipt":
            ident, digest, receipt = request["source_id"], request["source_sha256"], request["receipt"]
            if (type(ident) is int and 0 < ident <= 2**63 - 1 and isinstance(digest, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest) and type(receipt) is dict):
                rid = receipt.get("request_id")
                if isinstance(rid, str) and re.fullmatch(r"[a-z][a-z0-9-]{8,78}", rid):
                    try:
                        relay.validate_receipt(receipt, rid)
                    except relay.RelayError as exc:
                        raise BrokerError("invalid_request") from exc
                    return self._publish(ident, digest, receipt, deadline)
        raise BrokerError("invalid_request")

    def _read(self, deadline: float) -> dict:
        comments = self._scan(deadline)
        sources = [source for row in comments
                   if (source := self._source(row, active_only=False)) is not None]
        counts = Counter(source["request_id"] for source in sources)
        now = self.now()
        rows = [source for source in sources if counts[source["request_id"]] == 1
                and relay.parse_utc(source["issued_at"]) <= now < relay.parse_utc(source["expires_at"])
                and not self._receipts(comments, source["request_id"])]
        _encoded({"requests": rows}, MAX_RESPONSE_BYTES)
        verified = []
        with self._database() as db:
            for source in rows:
                _remaining(deadline)
                key = source["comment_id"], source["request_id"], source["source_sha256"]
                db.execute("INSERT OR IGNORE INTO sources(id, rid, sha256) VALUES (?, ?, ?)", key)
                if db.execute("SELECT 1 FROM sources WHERE id=? AND rid=? AND sha256=? AND attempted=0",
                              key).fetchone():
                    verified.append(source)
        return {"requests": verified}

    def _receipts(self, rows, rid):
        return relay.existing_receipts(
            [row for row in rows if _identity(row) in (self.publisher, (relay.OWNER, relay.OWNER_ID))
             and isinstance(row.get("body"), str) and len(row["body"]) <= relay.MAX_PUBLIC_COMMENT_BYTES], rid,
        )

    def _publish(self, ident: int, digest: str, receipt: dict, deadline: float) -> dict:
        rid = receipt["request_id"]
        body = relay.receipt_body(receipt)
        rows = self._scan(deadline)
        sources = [source["comment_id"] for row in rows
                   if (source := self._source(row, active_only=False)) is not None and source["request_id"] == rid]
        if sources != [ident]:
            raise BrokerError("source_unverified")
        source = self._source(self._request(deadline, f"{REPO_API}/issues/comments/{ident}"))
        if (source is None
                or (source["comment_id"], source["request_id"], source["source_sha256"]) != (ident, rid, digest)):
            raise BrokerError("source_unverified")
        prior = self._receipts(rows, rid)
        until_expiry = (relay.parse_utc(source["expires_at"]) - self.now()).total_seconds()
        if until_expiry <= 0:
            raise BrokerError("source_unverified")
        deadline = min(deadline, time.monotonic() + until_expiry)
        _remaining(deadline)
        with self._database() as db:
            admitted = db.execute("SELECT attempted FROM sources WHERE id=? AND rid=? AND sha256=?",
                                  (ident, rid, digest)).fetchone()
            if admitted is None:
                raise BrokerError("source_unverified")
            if prior:
                if len(prior) == 1 and prior[0].get("body") == body:
                    status = "already_published" if _identity(prior[0]) == self.publisher else "legacy_owner_receipt"
                    return {"status": status, "receipt_id": _comment_id(prior[0])}
                raise BrokerError("receipt_conflict")
            if admitted[0] or db.execute("UPDATE sources SET attempted=1 WHERE id=? AND attempted=0",
                                        (ident,)).rowcount != 1:
                raise BrokerError("unknown_outcome")
        # Commit the fence before POST. A crash between commit and POST also stays fenced.
        try:
            result = self._request(deadline, COMMENTS_API, {"body": body})
            if (isinstance(result, dict) and _comment_id(result) is not None
                    and result.get("body") == body and _identity(result) == self.publisher):
                confirmed = self._receipts(self._scan(deadline), rid)
                if (len(confirmed) == 1 and _comment_id(confirmed[0]) == _comment_id(result)
                        and confirmed[0]["body"] == body and _identity(confirmed[0]) == self.publisher):
                    return {"status": "published", "receipt_id": _comment_id(result)}
        except (relay.RelayError, OSError, ValueError, RecursionError):
            pass
        raise BrokerError("unknown_outcome")


if __name__ == "__main__":
    raise SystemExit("Production broker startup is gated on an approved transport and separate credential and OS identity.")
