from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "darwin", "requires macOS getpeereid")
class IsolationProbeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.uid = os.getuid()

    def test_same_uid_cannot_produce_cross_uid_evidence(self):
        probe = Path(__file__).resolve().parents[1] / "p3_isolation_probe.py"
        result = subprocess.run([
            sys.executable, "-B", str(probe), "seed", "--role", "broker",
            "--root", str(self.root), "--broker-uid", str(self.uid),
            "--worker-uid", str(self.uid), "--socket-gid", str(os.getgid()),
        ], capture_output=True, text=True, timeout=4)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"error": "distinct_nonroot_ids_required"', result.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_shared_directory_rejects_symlink_and_wrong_uid_or_mode(self):
        from p3_isolation_probe import ProbeError, verified_directory

        directory = self.root / "real"
        directory.mkdir(mode=0o710)
        symlink = self.root / "alias"
        symlink.symlink_to(directory)
        with self.assertRaises((ProbeError, OSError)):
            with verified_directory(symlink, self.uid, 0o710):
                self.fail("a directory symlink was accepted")
        for expected_uid, mode in ((self.uid + 1, 0o710), (self.uid, 0o700)):
            with self.subTest(expected_uid=expected_uid, mode=mode), self.assertRaises(ProbeError):
                with verified_directory(directory, expected_uid, mode):
                    self.fail("incorrect directory metadata was accepted")

    def test_synthetic_seed_cannot_follow_or_overwrite_a_marker(self):
        from p3_isolation_probe import seed_fixture, verify_fixture

        marker = self.root / "credential.fixture"
        other = self.root / "untouched"
        other.write_bytes(b"untouched")
        marker.symlink_to(other)
        with self.assertRaises(OSError):
            seed_fixture(self.root, self.uid)
        self.assertEqual(other.read_bytes(), b"untouched")
        marker.unlink()
        seed_fixture(self.root, self.uid)
        verify_fixture(self.root, self.uid)
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            seed_fixture(self.root, self.uid)

    def test_missing_fixture_does_not_count_as_permission_denial(self):
        from p3_isolation_probe import ProbeError, require_denied

        def open_missing():
            os.close(os.open(self.root / "missing", os.O_RDONLY))

        with self.assertRaises(ProbeError):
            require_denied(open_missing, "credential_read_not_denied")

        def denied():
            raise OSError(errno.EACCES, "fixture")

        require_denied(denied, "credential_read_not_denied")

    def test_socket_path_rejects_symlink_and_regular_file(self):
        from p3_isolation_probe import ProbeError, verify_socket

        share = self.root / "socket"
        share.mkdir(mode=0o710)
        path = share / "gh.sock"
        other = share / "other.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(other))
            other.chmod(0o660)
            verify_socket(other, self.uid, share.stat().st_gid)
            path.symlink_to(other)
            with self.assertRaises(ProbeError):
                verify_socket(path, self.uid, share.stat().st_gid)
        path.unlink()
        path.touch(mode=0o660)
        path.chmod(0o660)
        with self.assertRaises(ProbeError):
            verify_socket(path, self.uid, share.stat().st_gid)

    def test_real_broker_rejects_its_own_uid_when_it_expects_another(self):
        from p2_broker import GitHubBroker
        from p3_isolation_probe import FixtureTransport, verify_wrong_client

        share = self.root / "socket"
        share.mkdir(mode=0o710)
        transport = FixtureTransport()
        path = share / "gh.sock"
        with GitHubBroker(path, self.root, transport, worker_uid=self.uid + 1,
                          publisher=("fixture", 1), timeout=2) as broker:
            broker.listener.settimeout(2)
            verify_wrong_client(broker, path)
        self.assertEqual(transport.calls, [])

    def test_real_broker_accepts_pinned_server_and_refuses_wrong_pin(self):
        from p2_broker import GitHubBroker
        from p3_isolation_probe import FixtureTransport, verify_broker_handshake, verify_socket

        share = self.root / "socket"
        share.mkdir(mode=0o710)
        transport = FixtureTransport()
        path = share / "gh.sock"
        with GitHubBroker(path, self.root, transport, worker_uid=self.uid,
                          publisher=("fixture", 1), timeout=2) as broker:
            broker.listener.settimeout(2)
            verify_socket(path, self.uid, share.stat().st_gid)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: (broker.serve_one(), broker.serve_one()))
                verify_broker_handshake(path, self.uid, self.uid + 1)
                future.result(timeout=4)
        self.assertEqual(len(transport.calls), 2)
