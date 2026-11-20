from hashlib import sha256
import os
import stat
import subprocess

import pytest

from p2_workspace import FixtureCheck, Workspace, WorkspaceError, WorkspaceOutcomeUnknown


def test_create_does_not_require_unlink_after_publication(root, monkeypatch):

    def refuse_unlink(*args, **kwargs):
        raise PermissionError("simulated interruption between publication and staging cleanup")

    monkeypatch.setattr(os, "unlink", refuse_unlink)
    Workspace(root).execute("files.write", {"path": "created", "content": "complete"})
    assert (root / "created").stat().st_nlink == 1
    assert (root / "created").read_text() == "complete"


def test_mutation_after_unconfirmed_directory_sync_is_reported_as_uncertain(root, monkeypatch):
    fsync = os.fsync

    def fail_directory_sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("simulated durability failure")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory_sync)
    with pytest.raises(WorkspaceOutcomeUnknown):
        Workspace(root).execute("files.write", {"path": "created", "content": "complete"})
    assert (root / "created").read_text() == "complete"


@pytest.fixture
def root(tmp_path):
    root = tmp_path.resolve() / "fixture"
    root.mkdir(mode=0o700)
    return root


def test_write_is_create_only_and_patch_requires_the_current_hash(root):
    workspace = Workspace(root)
    (root / "src").mkdir()
    path = "src/example.txt"
    original = "first\n"
    digest = sha256(original.encode()).hexdigest()
    assert workspace.execute("files.write", {"path": path, "content": original}) == {"path": path, "sha256": digest}
    assert workspace.execute("files.read", {"path": path}) == {"path": path, "content": original, "sha256": digest}
    with pytest.raises(WorkspaceError):
        workspace.execute("files.write", {"path": path, "content": "overwrite"})
    with pytest.raises(WorkspaceError):
        workspace.execute("repo.apply_patch", {"path": path, "old_sha256": "0" * 64, "content": "overwrite"})
    assert (root / path).read_text() == original
    updated = "second\n"
    result = workspace.execute("repo.apply_patch", {"path": path, "old_sha256": digest, "content": updated})
    assert result == {"path": path, "sha256": sha256(updated.encode()).hexdigest()}
    assert (root / path).read_text() == updated


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/hosts", "./local", "dir//file", ".Git/config", "a\\b"])
def test_path_syntax_cannot_escape_the_root(root, path):
    workspace = Workspace(root)
    for operation, arguments in (("files.read", {}), ("files.write", {"content": "unsafe"})):
        with pytest.raises(WorkspaceError):
            workspace.execute(operation, {"path": path, **arguments})


def test_filesystem_aliases_and_special_files_are_refused(root):
    outside = root.parent / "outside.txt"
    outside.write_text("original")
    (root / "symlink").symlink_to(outside)
    (root / "directory").symlink_to(root.parent, target_is_directory=True)
    (root / "hardlink").hardlink_to(outside)
    os.mkfifo(root / "fifo")
    workspace = Workspace(root)
    for path in ("symlink", "directory/outside.txt", "hardlink", "fifo"):
        with pytest.raises(WorkspaceError):
            workspace.execute("files.read", {"path": path})
        with pytest.raises(WorkspaceError):
            workspace.execute("repo.apply_patch", {"path": path, "old_sha256": "0" * 64, "content": "unsafe"})
    assert outside.read_text() == "original"


def test_workspace_requires_a_private_real_root(root):
    alias = root.parent / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(WorkspaceError):
        Workspace(alias)
    root.chmod(0o750)
    with pytest.raises(WorkspaceError):
        Workspace(root)


def test_read_and_write_bound_payloads(root):
    workspace = Workspace(root)
    large = "x" * 100_000
    (root / "large").write_text(large)
    with pytest.raises(WorkspaceError):
        workspace.execute("files.read", {"path": "large"})
    with pytest.raises(WorkspaceError):
        workspace.execute("files.write", {"path": "new", "content": large})
    assert not (root / "new").exists()


def test_fixture_command_is_selected_locally_and_reads_changed_bytes(root):
    expected = sha256(b"expected\n").hexdigest()
    workspace = Workspace(root, fixture_checks={"content-check": FixtureCheck("fixture.txt", expected)})
    original = workspace.execute("files.write", {"path": "fixture.txt", "content": "original\n"})
    assert workspace.execute("test.run", {"command_id": "content-check"})["returncode"] == 1
    workspace.execute(
        "repo.apply_patch", {"path": "fixture.txt", "old_sha256": original["sha256"], "content": "expected\n"}
    )
    assert workspace.execute("test.run", {"command_id": "content-check"})["returncode"] == 0
    for target, arguments in (
        (workspace, {"command_id": "bash"}),
        (workspace, {"command_id": "content-check", "argv": ["/bin/sh"]}),
        (Workspace(root), {"command_id": "content-check"}),
    ):
        with pytest.raises(WorkspaceError):
            target.execute("test.run", arguments)


def test_inspect_reports_git_status_and_blocks_untrusted_config(root):
    subprocess.run(["/usr/bin/git", "init", "-q", str(root)], check=True, env={"GIT_CONFIG_NOSYSTEM": "1"})
    (root / "new.txt").write_text("data")
    workspace = Workspace(root)
    assert "?? new.txt" in workspace.execute("repo.inspect", {})["status"]
    marker = root / "invoked"
    config = root / ".git" / "config"
    with config.open("a") as handle:
        handle.write(f"\n[core]\n\tfsmonitor = /usr/bin/touch {marker}\n")
    with pytest.raises(WorkspaceError):
        workspace.execute("repo.inspect", {})
    assert not marker.exists()


def test_inspect_rejects_linked_git_metadata(root):
    (root / ".git").write_text("gitdir: ../admin-metadata\n")
    with pytest.raises(WorkspaceError):
        Workspace(root).execute("repo.inspect", {})


def test_inspect_rejects_git_metadata_links(root):
    subprocess.run(["/usr/bin/git", "init", "-q", str(root)], check=True, env={"GIT_CONFIG_NOSYSTEM": "1"})
    outside = root.parent / "outside.txt"
    outside.write_text("outside")
    exclude = root / ".git" / "info" / "exclude"
    exclude.unlink()
    exclude.symlink_to(outside)
    with pytest.raises(WorkspaceError, match="unsafe_git_metadata"):
        Workspace(root).execute("repo.inspect", {})


def test_git_status_output_is_bounded(root):
    subprocess.run(["/usr/bin/git", "init", "-q", str(root)], check=True, env={"GIT_CONFIG_NOSYSTEM": "1"})
    for number in range(200):
        (root / ("x" * 100 + str(number))).touch()
    with pytest.raises(WorkspaceError, match="git_status_too_large"):
        Workspace(root).execute("repo.inspect", {})
