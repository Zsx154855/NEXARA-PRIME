"""One-shot owner-grant preparation: P3 admission identity and owner bootstrap regressions.

All signatures use disposable test-only keys in a temporary directory.  No model,
production credentials, external network, or owner signing operation is used.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay
from p2_workspace import Workspace
from p3_private import Admission, Denied, Identity

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "prepare_grant.py"
BOOTSTRAP = ROOT / "approver_bootstrap.sh"


def git_repo(tmp_path):
    repo = tmp_path / "isolated-repo"
    repo.mkdir(mode=0o700)
    os.chmod(repo, 0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    subprocess.run(["/usr/bin/git", "init", "-q", "--template="], cwd=repo, env=env, check=True)
    (repo / "sample.txt").write_text("test-only\n")
    subprocess.run(["/usr/bin/git", "add", "--", "sample.txt"], cwd=repo, env=env, check=True)
    subprocess.run(["/usr/bin/git", "-c", "user.name=QA", "-c", "user.email=qa@example.invalid",
                    "commit", "-qm", "isolated baseline"], cwd=repo, env=env, check=True)
    return repo


def ephemeral_key(path):
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                   env={}, check=True, timeout=10)
    return " ".join(path.with_suffix(".pub").read_text().split()[:2])


def prepare(repo, approver_key):
    result = subprocess.run(
        [sys.executable, str(PREPARE), "--workspace", str(repo),
         "--requester-uid", str(os.geteuid()), "--public-key-file",
         str(approver_key.with_suffix(".pub"))],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


def test_generated_grant_is_accepted_by_real_p3_admission(tmp_path):
    repo = git_repo(tmp_path)
    owner_private = tmp_path / "test-approver"
    worker_private = tmp_path / "test-worker"
    approver_public = ephemeral_key(owner_private)
    worker_public = ephemeral_key(worker_private)
    bundle = prepare(repo, owner_private)
    tree = Workspace(repo)

    # A path string is not a P3 workspace identity; the binding must match exactly.
    assert bundle["contract"]["workspace"] == tree.binding()
    assert bundle["contract"]["workspace"] != str(repo)
    assert bundle["task"]["mission_id"] == bundle["contract"]["mission_id"]
    assert bundle["approver_public_key"] == approver_public
    assert bundle["sign_command"].find("<canonical grant json>") == -1
    assert bundle["contract"]["max_seconds"] == 20
    assert bundle["contract"]["budget_microusd"] == 0

    contract_file = tmp_path / "contract.json"
    relay.atomic_store(contract_file, bundle["contract"])
    signature = subprocess.check_output(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(owner_private),
         "-n", "nexara-p3-approval"],
        input=bundle["canonical_grant"].encode(),
        stderr=subprocess.DEVNULL, env={}, timeout=10,
    ).decode()
    request = {"task": bundle["task"], "grant": bundle["grant"], "signature": signature}
    admission = Admission(contract_file,
                          {"owner-approver": Identity(approver_public, "approver"),
                           "b1-worker": Identity(worker_public, "worker")},
                          tree.binding(), tree.head)
    assert admission.check(request, os.geteuid())["approval_id"] == bundle["grant"]["approval_id"]

    # A forged task must fail even if it reuses an otherwise legitimate signature.
    broken_task = dict(bundle["task"], task_id="different-task-id")
    with pytest.raises(Denied):
        admission.check(dict(request, task=broken_task), os.geteuid())


def test_each_prepared_request_has_fresh_identity_and_no_signature(tmp_path):
    repo = git_repo(tmp_path)
    private_key = tmp_path / "test-approver"
    ephemeral_key(private_key)
    first = prepare(repo, private_key)
    second = prepare(repo, private_key)

    assert first["contract"]["mission_id"] != second["contract"]["mission_id"]
    assert first["task"]["idempotency_key"] != second["task"]["idempotency_key"]
    assert first["grant"]["approval_id"] != second["grant"]["approval_id"]
    assert "signature" not in first
    assert first["grant"]["task_sha256"] != second["grant"]["task_sha256"]


def test_owner_bootstrap_refuses_noninteractive_context(tmp_path):
    dest = tmp_path / "owner-approver"
    result = subprocess.run(["/bin/sh", str(BOOTSTRAP), str(dest)], input=b"",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    assert result.returncode != 0
    assert not (dest / "approver_ed25519").exists()
    source = BOOTSTRAP.read_text()
    assert 'ssh-keygen -q -t ed25519 -N ""' not in source
    assert '[ ! -t 0 ]' in source
    assert 'ssh-keygen -y -P ""' in source
