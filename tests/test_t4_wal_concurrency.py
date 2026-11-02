"""T4 acceptance: the store must survive concurrent writers and a crash.

This is a new test written for the takeover, not an existing one. It asserts
three things the runtime claims but did not previously verify:

  1. the file really is in WAL mode, with a busy timeout
  2. two processes writing at once do not raise "database is locked"
  3. a SIGKILL in the middle of a write leaves an intact database
"""
from __future__ import annotations

import multiprocessing
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

from nexara_prime.db import SQLiteStore


def _writer(path: str, worker: int, count: int) -> None:
    store = SQLiteStore(path)
    for index in range(count):
        store.save_record(
            f"w{worker}-{index:04d}",
            "stress",
            {"worker": worker, "index": index},
            "2026-11-02T00:00:00Z",
        )


def _make_store() -> tuple[SQLiteStore, str]:
    root = tempfile.mkdtemp(prefix="wal-test-")
    path = os.path.join(root, "runtime.db")
    return SQLiteStore(path), path


def test_wal_and_busy_timeout_are_set():
    store, path = _make_store()
    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert str(mode).lower() == "wal", f"journal_mode is {mode!r}"
    assert int(timeout) >= 1000, f"busy_timeout is {timeout}"


def test_two_processes_write_without_locking_errors():
    store, path = _make_store()
    store.save_record("seed", "stress", {"seed": True}, "2026-11-02T00:00:00Z")

    ctx = multiprocessing.get_context("fork")
    workers = [ctx.Process(target=_writer, args=(path, n, 200)) for n in (1, 2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=120)
        assert worker.exitcode == 0, f"worker exited with {worker.exitcode}"

    total = store._conn.execute(
        "SELECT COUNT(*) FROM records WHERE record_type='stress'").fetchone()[0]
    assert total == 401, f"expected 401 records, found {total}"


def test_sigkill_mid_write_leaves_db_intact():
    store, path = _make_store()
    store.save_record("before", "stress", {"n": 0}, "2026-11-02T00:00:00Z")

    child = subprocess.Popen(
        [sys.executable, "-c", f"""
import os, signal, sys, time
sys.path.insert(0, {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))!r} + "/src")
from nexara_prime.db import SQLiteStore
s = SQLiteStore({path!r})
s._conn.execute("BEGIN IMMEDIATE")
s._conn.execute("INSERT INTO records (record_id, record_type, payload, created_at) VALUES ('ghost','stress','{{}}','2026-11-02T00:00:00Z')")
print("writing", flush=True)
time.sleep(120)
"""],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert child.stdout.readline().strip() == "writing"
    child.send_signal(signal.SIGKILL)
    child.wait(timeout=30)
    child.stdout.close()
    child.stderr.close()
    assert child.returncode == -9

    fresh = SQLiteStore(path)
    assert fresh._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    ghost = fresh._conn.execute(
        "SELECT COUNT(*) FROM records WHERE record_id='ghost'").fetchone()[0]
    assert ghost == 0, "the killed transaction must roll back"
    # the lock must be gone: a new writer proceeds immediately
    fresh.save_record("after", "stress", {"n": 1}, "2026-11-02T00:00:00Z")
    assert fresh.get_record("after") is not None
