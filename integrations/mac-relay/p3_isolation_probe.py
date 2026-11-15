"""Run an offline P2 broker handshake under two separately provisioned macOS UIDs."""
from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import sys

from p2_broker import BrokerError, COMMENTS_API, GitHubBroker, ISSUE_API, REPO_API, broker_call
from relay import ISSUE, RelayError


FIXTURE_BASE = Path("/private/tmp")
MARKER_NAME = "credential.fixture"
MARKER = b"Nexara P3 synthetic isolation fixture\n"
READ_REQUESTS = {"op": "read_requests"}
EXPECTED_READS = [("GET", ISSUE_API), ("GET", f"{COMMENTS_API}?per_page=100&page=1")]
SOCKET_TIMEOUT = 5


class ProbeError(ValueError):
    """A fixed, non-sensitive probe failure code."""


@contextmanager
def directory_fd(path: Path) -> Iterator[int]:
    if not path.is_absolute() or path.anchor != "/" or ".." in path.parts:
        raise ProbeError("noncanonical_path")
    flags = os.O_SEARCH | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def check_directory(info: os.stat_result, uid: int, mode: int, gid: int | None = None) -> None:
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode
            or (gid is not None and info.st_gid != gid)):
        raise ProbeError("directory_unverified")


@contextmanager
def verified_directory(path: Path, uid: int, mode: int, gid: int | None = None) -> Iterator[int]:
    with directory_fd(path) as fd:
        check_directory(os.fstat(fd), uid, mode, gid)
        yield fd


def verify_layout(root: Path, broker_uid: int, worker_uid: int, gid: int) -> None:
    if root.parent != FIXTURE_BASE or not re.fullmatch(r"nexara-p3-[A-Za-z0-9]{6,20}", root.name):
        raise ProbeError("fixture_root_unverified")
    with verified_directory(FIXTURE_BASE, 0, 0o1777), verified_directory(root, 0, 0o755) as fd:
        for name, uid, mode, directory_gid in (
            ("socket", broker_uid, 0o710, gid),
            ("broker-private", broker_uid, 0o700, None),
            ("worker-private", worker_uid, 0o700, None),
        ):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            check_directory(info, uid, mode, directory_gid)


def seed_fixture(directory: Path, uid: int) -> None:
    with verified_directory(directory, uid, 0o700) as fd:
        marker = os.open(MARKER_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(marker, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(MARKER)
    verify_fixture(directory, uid)


def verify_fixture(directory: Path, uid: int) -> None:
    with verified_directory(directory, uid, 0o700) as fd:
        marker = os.open(MARKER_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(marker, "rb") as fixture:
            info = os.fstat(fixture.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != len(MARKER)
                    or fixture.read(len(MARKER) + 1) != MARKER):
                raise ProbeError("synthetic_fixture_unverified")


def require_denied(operation: Callable[[], object], error: str) -> None:
    try:
        operation()
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EPERM):
            return
        raise ProbeError(error) from exc
    raise ProbeError(error)


def verify_isolation(other_private: Path) -> None:
    marker = other_private / MARKER_NAME

    def open_marker(mode: int) -> None:
        os.close(os.open(marker, mode | os.O_NOFOLLOW | os.O_NONBLOCK))

    require_denied(lambda: open_marker(os.O_RDONLY), "credential_read_not_denied")
    require_denied(lambda: open_marker(os.O_WRONLY), "credential_write_not_denied")
    require_denied(lambda: os.listdir(other_private), "credential_directory_listing_not_denied")


def verify_socket(path: Path, broker_uid: int, gid: int) -> None:
    with verified_directory(path.parent, broker_uid, 0o710, gid) as fd:
        info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != broker_uid or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != 0o660):
        raise ProbeError("socket_unverified")


class FixtureTransport:
    """Provide only two in-memory GET responses and record all calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, payload: dict | None, *, deadline: float, max_bytes: int) -> object:
        self.calls.append((method, path))
        if method == "GET" and payload is None:
            if path == ISSUE_API:
                return {"number": ISSUE, "state": "open", "repository_url": "https://api.github.com/" + REPO_API}
            if path == f"{COMMENTS_API}?per_page=100&page=1":
                return []
        raise ProbeError("unexpected_transport_call")


def verify_wrong_client(broker: GitHubBroker, socket_path: Path) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SOCKET_TIMEOUT)
        connection.connect(str(socket_path))
        connection.sendall(b'{"op":"read_requests"}')
        connection.shutdown(socket.SHUT_WR)
        broker.serve_one()
        with connection.makefile("rb") as response:
            if response.read(128) != b'{"error":"peer_denied"}':
                raise ProbeError("wrong_client_uid_not_denied")


def verify_broker_handshake(path: Path, broker_uid: int, wrong_uid: int) -> None:
    try:
        broker_call(path, READ_REQUESTS, broker_uid=wrong_uid, timeout=SOCKET_TIMEOUT)
    except BrokerError as exc:
        if str(exc) != "peer_denied":
            raise
    else:
        raise ProbeError("wrong_server_uid_not_denied")
    if broker_call(path, READ_REQUESTS, broker_uid=broker_uid, timeout=SOCKET_TIMEOUT) != {"requests": []}:
        raise ProbeError("authorized_read_unverified")


def emit(status: str, **fields: object) -> None:
    print(json.dumps({"status": status, "synthetic_only": True, **fields}, sort_keys=True), flush=True)


def run(args: argparse.Namespace, role: str) -> None:
    if sys.platform != "darwin":
        raise ProbeError("darwin_required")
    broker_uid, worker_uid, gid = args.broker_uid, args.worker_uid, args.socket_gid
    if broker_uid == worker_uid or not all(0 < number < 2**31 for number in (broker_uid, worker_uid, gid)):
        raise ProbeError("distinct_nonroot_ids_required")
    uid = broker_uid if role == "broker" else worker_uid
    if os.getuid() != uid or os.geteuid() != uid:
        raise ProbeError("role_uid_unverified")
    if gid != os.getegid() and gid not in os.getgroups():
        raise ProbeError("shared_group_required")
    verify_layout(args.root, broker_uid, worker_uid, gid)
    own = args.root / f"{role}-private"
    if args.command == "seed":
        seed_fixture(own, uid)
        emit("SEEDED", role=role, uid=uid)
        return

    verify_fixture(own, uid)
    verify_isolation(args.root / ("worker-private" if role == "broker" else "broker-private"))
    path = args.root / "socket" / "gh.sock"
    if role == "worker":
        if os.access(path.parent, os.W_OK):
            raise ProbeError("worker_socket_directory_writable")
        verify_socket(path, broker_uid, gid)
        verify_broker_handshake(path, broker_uid, worker_uid)
        emit("PASS_WORKER", uid=uid, broker_uid=broker_uid, wrong_server_uid_denied=True,
             broker_fixture_read_write_list_denied=True)
        return

    transport = FixtureTransport()
    with GitHubBroker(path, own, transport, worker_uid=worker_uid,
                      publisher=("synthetic-p3-fixture", 1), timeout=SOCKET_TIMEOUT) as broker:
        broker.listener.settimeout(SOCKET_TIMEOUT)
        verify_socket(path, broker_uid, gid)
        verify_wrong_client(broker, path)
        if transport.calls:
            raise ProbeError("wrong_client_reached_transport")
        broker.listener.settimeout(45)
        emit("READY", uid=uid, worker_uid=worker_uid)
        broker.serve_one()
        broker.listener.settimeout(SOCKET_TIMEOUT)
        broker.serve_one()
        if transport.calls != EXPECTED_READS:
            raise ProbeError("synthetic_read_boundary_unverified")
    emit("PASS_BROKER", uid=uid, worker_uid=worker_uid, wrong_client_uid_denied=True,
         worker_fixture_read_write_list_denied=True, synthetic_get_count=len(transport.calls))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seed", "serve", "verify"))
    parser.add_argument("--root", type=Path, required=True, help="root-owned /private/tmp/nexara-p3-XXXXXX")
    parser.add_argument("--broker-uid", type=int, required=True)
    parser.add_argument("--worker-uid", type=int, required=True)
    parser.add_argument("--socket-gid", type=int, required=True)
    parser.add_argument("--role", choices=("broker", "worker"), help="required for seed")
    args = parser.parse_args()
    role = {"seed": args.role, "serve": "broker", "verify": "worker"}[args.command]
    if role is None or (args.role and args.role != role):
        parser.error("provide the matching role for seed or omit --role for serve and verify")
    try:
        run(args, role)
    except (ProbeError, BrokerError) as exc:
        emit("FAIL", role=role, error=str(exc))
        return 2
    except TimeoutError:
        emit("FAIL", role=role, error="probe_deadline")
        return 2
    except (OSError, sqlite3.Error, RelayError) as exc:
        emit("FAIL", role=role, error="fixture_operation_failed", errno=getattr(exc, "errno", None))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
