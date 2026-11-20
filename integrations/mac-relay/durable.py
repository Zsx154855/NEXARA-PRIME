"""Durable, outbound-only GitHub worker for the existing read-only MCP gateway."""

import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
from functools import partial
import hashlib
import os
from pathlib import Path
import random
import signal
import sqlite3
import stat
import threading
from urllib.parse import urlencode
import uuid

import relay
from relay import GitHubResourceMissing, PublishRejected, RelayError


MAX_RESULT_BYTES = 64 * 1024
MAX_MCP_PER_HOUR = 12
OVERLAP = dt.timedelta(seconds=120)
ISSUE_API = f"repos/{relay.REPO}/issues/{relay.ISSUE}"


def utc(now):
    return now.isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(body):
    return hashlib.sha256(body.encode()).hexdigest()


def stopped(folder):
    return os.path.lexists(folder / "STOP")


@contextmanager
def private_fd(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600):
            raise RelayError("private_file_unverified")
        yield fd
    finally:
        os.close(fd)


class Mailbox(relay.GitHubAPI):
    def assert_actor(self):
        actor = self.request("user")
        if actor.get("id") != self.actor_id or actor.get("login") != relay.OWNER:
            raise RelayError("github_owner_identity_unverified")

    def assert_open(self):
        if self.request(ISSUE_API).get("state") != "open":
            raise RelayError("issue_closed")

    def comments(self, since=None):
        if since is None:
            return super().comments()
        out = []
        for page in range(1, 6):
            query = urlencode({"since": since, "page": page, "per_page": 100})
            rows = self.request(f"{self.base}?{query}")
            if not isinstance(rows, list):
                raise RelayError("github_invalid_comments")
            out.extend(rows)
            if len(rows) < 100:
                return out
        raise RelayError("github_scan_incomplete")

    def comment(self, ident):
        row = self.request(f"repos/{relay.REPO}/issues/comments/{int(ident)}", distinguish_missing=True)
        if (row.get("id") != ident
                or row.get("issue_url") != f"https://api.github.com/{ISSUE_API}"):
            raise RelayError("comment_target_unverified")
        return row


class Controller:
    database_name = "durable.sqlite3"

    def __init__(self, folder, api, cfg, *, now=None, invoke=None, halt=None):
        self.folder, self.api, self.cfg = folder, api, cfg
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.invoke = invoke or partial(relay.call_mcp, require_readonly=True)
        self.halt = halt or threading.Event()
        self.lease = uuid.uuid4().hex
        self.db = None

    def __enter__(self):
        info = self.folder.stat()
        if (self.folder != self.folder.resolve() or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise RelayError("private_directory_unverified")
        self.lock = private_fd(self.folder / "relay.lock")
        fd = self.lock.__enter__()
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            db_path = self.folder / self.database_name
            for suffix in ("-journal", "-wal", "-shm"):
                sidecar = db_path.with_name(db_path.name + suffix)
                if os.path.lexists(sidecar):
                    with private_fd(sidecar):
                        pass
            with private_fd(db_path):
                self.db = sqlite3.connect(db_path)
            self.db.row_factory = sqlite3.Row
            self.db.executescript("""
                PRAGMA journal_mode=DELETE;
                PRAGMA synchronous=FULL;
                PRAGMA fullfsync=ON;
                PRAGMA max_page_count=16384;
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks(
                  rid TEXT PRIMARY KEY, source_id INTEGER NOT NULL UNIQUE,
                  source_hash TEXT NOT NULL, request TEXT NOT NULL, expires TEXT NOT NULL,
                  phase TEXT NOT NULL, lease TEXT, raw_result TEXT, result_hash TEXT,
                  receipt TEXT, receipt_id INTEGER, failure TEXT, attempts INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS observed_receipts(
                  rid TEXT NOT NULL, comment_id INTEGER NOT NULL, PRIMARY KEY(rid, comment_id)
                );
                CREATE TABLE IF NOT EXISTS events(
                  seq INTEGER PRIMARY KEY, rid TEXT NOT NULL,
                  at TEXT NOT NULL, phase TEXT NOT NULL, code TEXT
                );
                CREATE INDEX IF NOT EXISTS events_phase_at ON events(phase, at);
            """)
            self.recover()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        try:
            if self.db is not None:
                self.db.close()
        finally:
            self.lock.__exit__(None, None, None)

    def job(self, rid):
        return self.db.execute("SELECT * FROM tasks WHERE rid=?", (rid,)).fetchone()

    def event(self, rid, phase, code=None):
        self.db.execute("INSERT INTO events(rid,at,phase,code) VALUES (?,?,?,?)",
                        (rid, utc(self.now()), phase, code))

    def phase(self, rid, phase, code=None):
        self.db.execute("UPDATE tasks SET phase=?,failure=? WHERE rid=?", (phase, code, rid))
        self.event(rid, phase, code)

    def recover(self):
        with self.db:
            for row in self.db.execute("SELECT rid,phase FROM tasks WHERE phase IN "
                                       "('EXECUTING','PUBLISHING','UNKNOWN_OUTCOME')").fetchall():
                if row["phase"] == "EXECUTING":
                    self.phase(row["rid"], "QUARANTINED", "interrupted_mcp")
                if row["phase"] == "PUBLISHING":
                    self.phase(row["rid"], "UNKNOWN_OUTCOME", "interrupted_publish")
                if row["phase"] == "UNKNOWN_OUTCOME" and self.job(row["rid"])["receipt"] is None:
                    self.phase(row["rid"], "QUARANTINED", "unverified_mcp")

    def sync(self):
        cursor = self.db.execute("SELECT value FROM meta WHERE key='cursor'").fetchone()
        now = self.now()
        high = relay.parse_utc(cursor[0]) if cursor else None
        if high and now < high - OVERLAP:
            raise RelayError("clock_moved_backwards")
        rows = self.api.comments(utc(high - OVERLAP) if high else None)
        legacy = relay.state_read(self.folder / "state.json")["jobs"]
        with self.db:
            for row in rows:
                self.observe(row, now, legacy)
            if not high or now > high:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('cursor',?)", (utc(now),))

    def observe(self, row, now, legacy):
        body, ident = row.get("body"), row.get("id")
        if not isinstance(body, str) or type(ident) is not int or ident <= 0:
            return
        if body.startswith(relay.RECEIPT_MARKER + "\n") and len(body) <= relay.MAX_PUBLIC_COMMENT_BYTES:
            author = row.get("user")
            if (not isinstance(author, dict) or author.get("id") != self.api.actor_id
                    or author.get("login") != self.cfg["owner"]):
                return
            try:
                receipt = relay.strict_json(body.split("\n", 1)[1])
                rid = receipt.get("request_id") if isinstance(receipt, dict) else None
                relay.validate_receipt(receipt, rid)
                if isinstance(rid, str) and len(rid) <= 79:
                    self.db.execute("INSERT OR IGNORE INTO observed_receipts VALUES (?,?)", (rid, ident))
            except (RelayError, ValueError, RecursionError):
                pass
            return
        try:
            request = relay.request_from_comment(row, self.cfg["owner"], now, active_only=False)
            if request is None:
                return
            created = relay.parse_utc(row.get("created_at"))
            updated = relay.parse_utc(row.get("updated_at"))
            issued = relay.parse_utc(request["issued_at"])
            expires = relay.parse_utc(request["expires_at"])
        except RelayError:
            return
        rid, sha = request["request_id"], digest(body)
        prior = self.job(rid)
        if prior:
            if ((prior["source_id"], prior["source_hash"]) != (ident, sha) or created != updated) and prior["phase"] in (
                    "VALIDATED", "CLAIMED", "RESULT_STAGED"):
                self.phase(rid, "REJECTED", "source_changed_or_duplicate")
            return
        if self.db.execute("SELECT 1 FROM tasks WHERE source_id=?", (ident,)).fetchone():
            return
        self.db.execute("INSERT INTO tasks(rid,source_id,source_hash,request,expires,phase) VALUES (?,?,?,?,?,?)",
                        (rid, ident, sha, relay.json_canonical(request), utc(expires), "DISCOVERED"))
        self.event(rid, "DISCOVERED")
        if rid in legacy:
            self.phase(rid, "QUARANTINED", "legacy_journal_present")
        elif created != updated or not issued <= created < expires or issued > now:
            self.phase(rid, "REJECTED", "source_timestamp_unverified")
        elif now >= expires:
            self.phase(rid, "EXPIRED")
        else:
            self.phase(rid, "VALIDATED")

    def receipt_ids(self, rid):
        return [row[0] for row in self.db.execute(
            "SELECT comment_id FROM observed_receipts WHERE rid=? ORDER BY comment_id LIMIT 2", (rid,))]

    def verify(self, row, ident):
        rid, body = row["rid"], row["receipt"]
        try:
            result = self.api.comment(ident)
        except GitHubResourceMissing:
            with self.db:
                self.phase(rid, "QUARANTINED", "published_receipt_missing")
            return "QUARANTINED"
        author = result.get("user") or {}
        if (result.get("id") != ident or result.get("body") != body
                or author.get("id") != self.api.actor_id or author.get("login") != self.cfg["owner"]):
            with self.db:
                self.phase(rid, "QUARANTINED", "receipt_mismatch")
            return "QUARANTINED"
        with self.db:
            self.db.execute("UPDATE tasks SET receipt_id=? WHERE rid=?", (ident, rid))
            self.phase(rid, "VERIFIED")
            self.phase(rid, "COMPLETED")
        return "COMPLETED"

    def authorized(self, row):
        rid = row["rid"]
        self.sync()
        current = self.job(rid)
        if current["phase"] != row["phase"]:
            return current["phase"]
        if self.receipt_ids(rid):
            return "QUARANTINED"
        if rid in relay.state_read(self.folder / "state.json")["jobs"]:
            return "QUARANTINED"
        try:
            source = self.api.comment(row["source_id"])
        except GitHubResourceMissing:
            return "REJECTED"
        body = source.get("body")
        now = self.now()
        if now >= relay.parse_utc(row["expires"]):
            return "EXPIRED"
        if (not isinstance(body, str) or digest(body) != row["source_hash"]
                or source.get("updated_at") != source.get("created_at")
                or relay.request_from_comment(source, self.cfg["owner"], now) is None):
            return "REJECTED"
        return None

    def tick(self):
        if self.halt.is_set() or stopped(self.folder):
            return "STOPPED"
        self.api.assert_open()
        self.sync()
        # Pending publications can be verified even after the source request expires.
        pending = self.db.execute("""
            SELECT * FROM tasks WHERE receipt IS NOT NULL
              AND (phase='PUBLISHED' OR (phase='UNKNOWN_OUTCOME' AND EXISTS (
                SELECT 1 FROM observed_receipts AS r WHERE r.rid=tasks.rid)))
            ORDER BY source_id LIMIT 1
        """).fetchall()
        for row in pending:
            receipts = self.receipt_ids(row["rid"])
            if len(receipts) > 1 or (receipts and row["receipt_id"] not in (None, receipts[0])):
                with self.db:
                    self.phase(row["rid"], "QUARANTINED", "conflicting_receipts")
                return "QUARANTINED"
            ident = row["receipt_id"] or (receipts[0] if receipts else None)
            if ident is not None:
                return self.verify(row, ident)
        row = self.db.execute("SELECT * FROM tasks WHERE phase IN "
                              "('VALIDATED','CLAIMED','RESULT_STAGED') ORDER BY source_id LIMIT 1").fetchone()
        if row is None:
            return "IDLE"
        rid = row["rid"]
        if row["phase"] == "RESULT_STAGED":
            return self.publish(row)
        decision = self.authorized(row)
        if decision:
            with self.db:
                self.phase(rid, decision)
            return decision
        cutoff = utc(self.now() - dt.timedelta(hours=1))
        calls = self.db.execute("SELECT count(*) FROM events WHERE phase='EXECUTING' AND at>?", (cutoff,)).fetchone()[0]
        if calls >= MAX_MCP_PER_HOUR:
            return "HOURLY_LIMIT"
        if self.halt.is_set() or stopped(self.folder):
            return "STOPPED"
        with self.db:
            self.db.execute("UPDATE tasks SET lease=? WHERE rid=?", (self.lease, rid))
            self.phase(rid, "CLAIMED")
        with self.db:
            self.phase(rid, "EXECUTING")
        request = relay.strict_json(row["request"])
        try:
            raw = self.invoke(self.cfg["mcp_argv"], request["tool"])
            result = relay.json_canonical(raw)
            if not isinstance(raw, dict) or len(result.encode()) > MAX_RESULT_BYTES:
                raise RelayError("mcp_result_unverified")
            if raw.get("status") not in ("PASS", "NOT_VERIFIED"):
                with self.db:
                    self.db.execute("UPDATE tasks SET raw_result=?,result_hash=? WHERE rid=?",
                                    (result, digest(result), rid))
                    self.phase(rid, "BLOCKED", "mcp_status_unverified")
                return "BLOCKED"
            receipt = relay.redacted_receipt(request, True, raw, self.cfg["field_paths"].get(request["tool"], {}))
            relay.validate_receipt(receipt, rid)
        except (RelayError, OSError, ValueError, TypeError, RecursionError):
            with self.db:
                self.phase(rid, "UNKNOWN_OUTCOME", "mcp_unverified")
            return "UNKNOWN_OUTCOME"
        with self.db:
            self.db.execute("UPDATE tasks SET raw_result=?,result_hash=?,receipt=? WHERE rid=?",
                            (result, digest(result), relay.receipt_body(receipt), rid))
            self.phase(rid, "RESULT_STAGED")
        return self.publish(self.job(rid))

    def publish(self, row):
        rid = row["rid"]
        self.api.assert_open()
        self.api.assert_actor()
        decision = self.authorized(row)
        if decision:
            with self.db:
                self.phase(rid, decision)
            return decision
        if (not row["raw_result"] or digest(row["raw_result"]) != row["result_hash"]
                or not row["receipt"].startswith(relay.RECEIPT_MARKER + "\n")):
            raise RelayError("staged_integrity_failure")
        request = relay.strict_json(row["request"])
        raw = relay.strict_json(row["raw_result"])
        expected = relay.redacted_receipt(request, True, raw, self.cfg["field_paths"].get(request["tool"], {}))
        relay.validate_receipt(expected, rid)
        if row["receipt"] != relay.receipt_body(expected):
            raise RelayError("staged_receipt_mismatch")
        if self.halt.is_set() or stopped(self.folder):
            return "STOPPED"
        if row["attempts"] >= 3:
            with self.db:
                self.phase(rid, "BLOCKED", "publish_attempt_limit")
            return "BLOCKED"
        with self.db:
            self.db.execute("UPDATE tasks SET attempts=attempts+1 WHERE rid=?", (rid,))
            self.phase(rid, "PUBLISHING")
        stopping = self.halt.is_set() or stopped(self.folder)
        if stopping or self.now() >= relay.parse_utc(row["expires"]):
            with self.db:
                self.phase(rid, "RESULT_STAGED" if stopping else "EXPIRED", "post_not_dispatched")
            return "STOPPED" if stopping else "EXPIRED"
        try:
            posted = self.api.post(row["receipt"])
            ident = posted.get("id")
            if type(ident) is not int or ident <= 0:
                raise RelayError("post_id_unverified")
        except PublishRejected:
            with self.db:
                self.phase(rid, "RESULT_STAGED", "github_post_rejected")
            return "RESULT_STAGED"
        except (RelayError, OSError, ValueError, AttributeError):
            with self.db:
                self.phase(rid, "UNKNOWN_OUTCOME", "publish_unverified")
            return "UNKNOWN_OUTCOME"
        with self.db:
            self.db.execute("UPDATE tasks SET receipt_id=? WHERE rid=?", (ident, rid))
            self.phase(rid, "PUBLISHED")
        return self.verify(self.job(rid), ident)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--exit-after-completion", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    halt = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: halt.set())
    try:
        path = args.config.absolute()
        cfg = relay.load_config(path)
        if stopped(path.parent):
            print("STOPPED", flush=True)
            return 0
        with Controller(path.parent, None, cfg, halt=halt) as worker:
            failures = 0
            while True:
                try:
                    if worker.api is None and not halt.is_set() and not stopped(path.parent):
                        worker.api = Mailbox(cfg["repo"], cfg["issue"])
                    status = worker.tick()
                    failures = failures + 1 if status == "RESULT_STAGED" else 0
                except (RelayError, OSError, ValueError):
                    status = "TEMPORARILY_BLOCKED"
                    failures += 1
                relay.atomic_store(path.parent / "health.json", {
                    "at": utc(worker.now()), "status": status, "consecutive_failures": failures})
                print(status, flush=True)
                if (not args.foreground or status == "STOPPED" or halt.is_set()
                        or (args.exit_after_completion and status == "COMPLETED")):
                    return 0 if status in ("COMPLETED", "IDLE", "STOPPED") else 3
                base = cfg["poll_seconds"]
                delay = max(base, min(900, base * 2 ** min(failures, 5)))
                halt.wait(delay + random.uniform(0, min(5, delay * 0.1)))
    except (RelayError, OSError, ValueError, sqlite3.Error) as exc:
        print("CONTROLLER_BLOCKED=" + type(exc).__name__, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
