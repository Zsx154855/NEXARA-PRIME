"""Local controlled tools for a private workspace selected by trusted configuration."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import os
from pathlib import Path
import re
import secrets
import selectors
import stat
import subprocess
import sys
import time


MAX_FILE_BYTES = 64 * 1024
MAX_GIT_OUTPUT = 16 * 1024
COMMAND_TIMEOUT = 5
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
_PATH_COMPONENT = re.compile(r"[a-zA-Z0-9_.-]{1,128}")
_DIGEST = re.compile(r"[a-f0-9]{64}")
_COMMAND_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
_STAGING_PREFIX = ".nexara-p2-"
_SCHEMAS = {
    "repo.inspect": frozenset(),
    "files.read": frozenset({"path"}),
    "files.write": frozenset({"path", "content"}),
    "repo.apply_patch": frozenset({"path", "old_sha256", "content"}),
    "test.run": frozenset({"command_id"}),
}
_GIT_CORE_CONFIG = re.compile(
    r"(?:repositoryformatversion[ \t]*=[ \t]*0|bare[ \t]*=[ \t]*false|"
    r"(?:filemode|logallrefupdates|ignorecase|precomposeunicode|symlinks)[ \t]*=[ \t]*(?:true|false))",
    re.IGNORECASE,
)
_FIXTURE_CHECK = (
    "import hashlib, sys\n"
    "ok = hashlib.sha256(sys.stdin.buffer.read()).hexdigest() == sys.argv[1]\n"
    "print('fixture content matched' if ok else 'fixture content differed')\n"
    "raise SystemExit(0 if ok else 1)\n"
)


class WorkspaceError(ValueError):
    """The workspace request was refused or could not be executed."""


class WorkspaceOutcomeUnknown(WorkspaceError):
    """A mutation became visible before its durability was confirmed."""


@dataclass(frozen=True)
class FixtureCheck:
    path: str
    sha256: str


def _path_parts(path: object) -> list[str]:
    if not isinstance(path, str) or len(path) > 512:
        raise WorkspaceError("invalid_path")
    parts = path.split("/")
    for part in parts:
        if (
            not _PATH_COMPONENT.fullmatch(part)
            or part in (".", "..")
            or part.lower() == ".git"
            or part.lower().startswith(_STAGING_PREFIX)
        ):
            raise WorkspaceError("invalid_path")
    return parts


def _digest(value: object) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise WorkspaceError("invalid_sha256")
    return value


def _payload(content: object) -> bytes:
    if not isinstance(content, str) or len(content) > MAX_FILE_BYTES:
        raise WorkspaceError("invalid_content")
    try:
        data = content.encode("utf-8")
    except UnicodeError as exc:
        raise WorkspaceError("invalid_content") from exc
    if len(data) > MAX_FILE_BYTES or b"\0" in data:
        raise WorkspaceError("invalid_content")
    return data


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _safe_regular(info: os.stat_result) -> bool:
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and info.st_uid == os.geteuid()
        and not (info.st_mode & 0o7022)
    )


def _safe_directory(info: os.stat_result) -> bool:
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and not (info.st_mode & 0o7022)


def _read_regular(parent: int, name: str) -> tuple[bytes, os.stat_result]:
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not _safe_regular(before) or before.st_dev != os.fstat(parent).st_dev or before.st_size > MAX_FILE_BYTES:
        raise WorkspaceError("unsafe_or_oversized_file")
    with os.fdopen(os.open(name, _FILE_FLAGS, dir_fd=parent), "rb") as handle:
        opened = os.fstat(handle.fileno())
        if _identity(opened) != _identity(before) or not _safe_regular(opened):
            raise WorkspaceError("unsafe_or_oversized_file")
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise WorkspaceError("unsafe_or_oversized_file")
    return data, opened


def _rename_exclusive(parent: int, source: str, target: str) -> None:
    # A single no-replace rename prevents a crash from leaving a published hardlink pair.
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = getattr(libc, "renameatx_np", None)
        flags = 0x00000004  # RENAME_EXCL in Darwin's sys/stdio.h.
    elif sys.platform == "linux":
        rename = getattr(libc, "renameat2", None)
        flags = 1  # RENAME_NOREPLACE in Linux's fs.h.
    else:
        rename = None
    if rename is None:
        raise WorkspaceError("atomic_create_unavailable")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(source), parent, os.fsencode(target), flags) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


class Workspace:
    def __init__(self, root: Path, *, fixture_checks: Mapping[str, FixtureCheck] | None = None):
        self._root = Path(root)
        with self._root_fd() as fd:
            self._root_identity = _identity(os.fstat(fd))
        self._fixture_checks = dict(fixture_checks or {})
        for command_id, check in self._fixture_checks.items():
            if (
                not isinstance(command_id, str)
                or not _COMMAND_ID.fullmatch(command_id)
                or not isinstance(check, FixtureCheck)
            ):
                raise WorkspaceError("invalid_fixture_catalog")
            _path_parts(check.path)
            _digest(check.sha256)

    @contextmanager
    def _root_fd(self) -> Iterator[int]:
        if not self._root.is_absolute() or self._root.anchor != "/" or ".." in self._root.parts:
            raise WorkspaceError("invalid_workspace_root")
        fd = os.open("/", _DIRECTORY_FLAGS)
        try:
            for component in self._root.parts[1:]:
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            if not _safe_directory(info) or stat.S_IMODE(info.st_mode) != 0o700:
                raise WorkspaceError("workspace_root_must_be_private")
            yield fd
        except OSError as exc:
            raise WorkspaceError("workspace_filesystem_error") from exc
        finally:
            os.close(fd)

    @staticmethod
    @contextmanager
    def _file_parent(root_fd: int, path: object) -> Iterator[tuple[int, str]]:
        *parts, name = _path_parts(path)
        fd = os.dup(root_fd)
        try:
            root_device = os.fstat(root_fd).st_dev
            for part in parts:
                child = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if not _safe_directory(info) or info.st_dev != root_device:
                    raise WorkspaceError("unsafe_directory")
            yield fd, name
        finally:
            os.close(fd)

    def execute(self, operation: str, args: dict) -> dict:
        if (
            not isinstance(operation, str)
            or operation not in _SCHEMAS
            or not isinstance(args, dict)
            or args.keys() != _SCHEMAS[operation]
        ):
            raise WorkspaceError("invalid_operation_or_arguments")
        with self._root_fd() as root_fd:
            if _identity(os.fstat(root_fd)) != self._root_identity:
                raise WorkspaceError("workspace_root_replaced")
            # Serialize checks and file mutations across Workspace instances and processes.
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if operation == "repo.inspect":
                return {"status": self._inspect(root_fd)}
            if operation == "test.run":
                return self._run_fixture(root_fd, args["command_id"])
            path = args["path"]
            with self._file_parent(root_fd, path) as (parent, name):
                if operation == "files.read":
                    data, _ = _read_regular(parent, name)
                    try:
                        content = data.decode("utf-8")
                    except UnicodeError as exc:
                        raise WorkspaceError("invalid_content") from exc
                    return {"path": path, "content": content, "sha256": sha256(data).hexdigest()}
                data = _payload(args["content"])
                previous = None
                if operation == "repo.apply_patch":
                    expected = _digest(args["old_sha256"])
                    old_data, previous = _read_regular(parent, name)
                    if sha256(old_data).hexdigest() != expected:
                        raise WorkspaceError("stale_file_hash")
                self._publish(parent, name, data, previous)
                return {"path": path, "sha256": sha256(data).hexdigest()}

    @staticmethod
    def _publish(parent: int, name: str, data: bytes, previous: os.stat_result | None) -> None:
        temporary = _STAGING_PREFIX + secrets.token_hex(16)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = os.open(temporary, flags, 0o600, dir_fd=parent)
        published = False
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fchmod(handle.fileno(), 0o600 if previous is None else stat.S_IMODE(previous.st_mode))
                os.fsync(handle.fileno())
            if previous is None:
                _rename_exclusive(parent, temporary, name)
            else:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if (
                    not _safe_regular(current)
                    or _identity(current) != _identity(previous)
                    or current.st_ctime_ns != previous.st_ctime_ns
                ):
                    raise WorkspaceError("stale_file_identity")
                os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
            published = True
            os.fsync(parent)
        except OSError as exc:
            if published:
                raise WorkspaceOutcomeUnknown("workspace_mutation_durability_unconfirmed") from exc
            raise
        finally:
            if not published:
                os.unlink(temporary, dir_fd=parent)

    def _run_fixture(self, root_fd: int, command_id: object) -> dict:
        if not isinstance(command_id, str) or command_id not in self._fixture_checks:
            raise WorkspaceError("test_command_not_allowed")
        check = self._fixture_checks[command_id]
        with self._file_parent(root_fd, check.path) as (parent, name):
            data, _ = _read_regular(parent, name)
        # Only this fixed check can run under the current identity. Repo tests need an OS boundary.
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c", _FIXTURE_CHECK, check.sha256],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd="/",
                env={},
                close_fds=True,
                shell=False,
                timeout=COMMAND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceError("fixture_check_timeout") from exc
        if result.returncode not in (0, 1) or result.stdout not in (
            b"fixture content matched\n",
            b"fixture content differed\n",
        ):
            raise WorkspaceError("fixture_check_failed_to_start")
        return {"command_id": command_id, "returncode": result.returncode, "output": result.stdout.decode().strip()}

    def head(self) -> str:
        with self._root_fd() as root_fd:
            if _identity(os.fstat(root_fd)) != self._root_identity:
                raise WorkspaceError("workspace_root_replaced")
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            value = self._inspect(root_fd, head_only=True).strip()
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
                raise WorkspaceError("invalid_git_head")
            return value

    def binding(self) -> str:
        with self._root_fd() as root_fd:
            info = os.fstat(root_fd)
            if _identity(info) != self._root_identity:
                raise WorkspaceError("workspace_root_replaced")
            return sha256(f"{self._root}:{info.st_dev}:{info.st_ino}".encode()).hexdigest()

    def has_fixture_check(self, command_id: str, path: str, expected_sha256: str) -> bool:
        return self._fixture_checks.get(command_id) == FixtureCheck(path, expected_sha256)

    def _inspect(self, root_fd: int, *, head_only=False) -> str:
        git_fd = os.open(".git", _DIRECTORY_FLAGS, dir_fd=root_fd)
        try:
            git_info = os.fstat(git_fd)
            if not _safe_directory(git_info) or git_info.st_dev != os.fstat(root_fd).st_dev:
                raise WorkspaceError("unsafe_git_metadata")
            config, _ = _read_regular(git_fd, "config")
            _validate_git_config(config)
            _validate_git_metadata(git_fd, git_info.st_dev, [4096])
        finally:
            os.close(git_fd)
        if _identity(os.stat(self._root, follow_symlinks=False)) != _identity(os.fstat(root_fd)):
            raise WorkspaceError("workspace_root_replaced")
        return _git_status(root_fd, head_only=head_only)


def _validate_git_config(config: bytes) -> None:
    try:
        text = config.decode("ascii")
    except UnicodeError as exc:
        raise WorkspaceError("unsafe_git_config") from exc
    section = False
    for line in text.splitlines():
        line = line.strip(" \t")
        if not line:
            continue
        if line.lower() == "[core]":
            section = True
        elif not section or not _GIT_CORE_CONFIG.fullmatch(line):
            raise WorkspaceError("unsafe_git_config")
    if not section:
        raise WorkspaceError("unsafe_git_config")


def _validate_git_metadata(fd: int, device: int, remaining: list[int], depth: int = 0) -> None:
    if depth > 16:
        raise WorkspaceError("unsafe_git_metadata")
    with os.scandir(fd) as entries:
        for entry in entries:
            remaining[0] -= 1
            info = entry.stat(follow_symlinks=False)
            if (
                remaining[0] < 0
                or info.st_dev != device
                or entry.name.casefold()
                in {
                    "alternates",
                    "http-alternates",
                    "commondir",
                    "gitdir",
                    "config.worktree",
                }
            ):
                raise WorkspaceError("unsafe_git_metadata")
            if _safe_directory(info):
                child = os.open(entry.name, _DIRECTORY_FLAGS, dir_fd=fd)
                try:
                    _validate_git_metadata(child, device, remaining, depth + 1)
                finally:
                    os.close(child)
            elif not _safe_regular(info):
                raise WorkspaceError("unsafe_git_metadata")


def _git_status(root_fd: int, *, head_only=False) -> str:
    # Bind Git's cwd to the validated directory instead of reopening its pathname.
    bootstrap = (
        "import os,sys; fd=int(sys.argv[1]); os.fchdir(fd); os.close(fd); "
        "os.execv(sys.argv[2],sys.argv[2:])"
    )
    argv = [
        sys.executable, "-I", "-B", "-c", bootstrap, str(root_fd),
        "/usr/bin/git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        "--no-optional-locks",
    ]
    argv.extend(("--no-replace-objects", "rev-parse", "--verify", "HEAD^{commit}") if head_only else (
        "status", "--porcelain=v1", "--branch", "--no-renames", "--ignore-submodules=all",
    ))
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/dev/null",
        "XDG_CONFIG_HOME": "/dev/null",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_EXEC_PATH": "/dev/null",
    }
    with subprocess.Popen(
        argv,
        cwd="/",
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        pass_fds=(root_fd,),
        shell=False,
    ) as process:
        try:
            assert process.stdout is not None
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + COMMAND_TIMEOUT
                data = bytearray()
                while selector.select(max(0, deadline - time.monotonic())):
                    chunk = os.read(process.stdout.fileno(), min(4096, MAX_GIT_OUTPUT + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > MAX_GIT_OUTPUT:
                        raise WorkspaceError("git_status_too_large")
                else:
                    raise WorkspaceError("git_status_timeout")
                if process.wait(timeout=max(0, deadline - time.monotonic())):
                    raise WorkspaceError("git_status_failed")
                return data.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceError("git_status_timeout") from exc
        finally:
            if process.poll() is None:
                process.kill()
