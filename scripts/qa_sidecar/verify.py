#!/usr/bin/env python3
"""Read-only PR evidence checker; it never certifies independent QA identity."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
HEXLOG = re.compile(r"([0-9a-f]{64}) [ *](.+)\Z")
FILES = (
    "focused.log", "full.log", "commit-sha.txt", "git-status.txt",
    "final-report.txt", "log-sha256.txt",
)
SIGN_NAMESPACE = "nexara-qa-sidecar-v1"


class Blocked(Exception):
    pass


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def read_file(path):
    if path.is_symlink() or not path.is_file():
        raise Blocked("missing_or_symlink:" + path.name)
    return path.read_bytes()


def exact_fields(body):
    out = {}
    for line in body.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k in out:
            raise Blocked("duplicate_field:" + k)
        out[k] = v.strip()
    return out


def git(repo, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True,
            text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Blocked("git_unavailable") from exc
    if result.returncode:
        raise Blocked("git_failure:" + args[0])
    return result.stdout.strip()


def load_policy(path, pinned_hash, repo, evidence):
    if not SHA256.fullmatch(pinned_hash):
        raise Blocked("invalid_policy_pin")
    if path.is_symlink() or not path.is_file():
        raise Blocked("policy_missing_or_symlink")
    if path.resolve() == repo or repo in path.resolve().parents or path.resolve() == evidence or evidence in path.resolve().parents:
        raise Blocked("policy_not_external")
    raw = read_file(path)
    if sha256(raw) != pinned_hash:
        raise Blocked("policy_digest_mismatch")
    policy = json.loads(raw)
    if not isinstance(policy, dict) or set(policy) != {
        "schema", "repository", "commit_sha", "expected_counts", "expected_log_sha256", "signer"
    }:
        raise Blocked("policy_schema_mismatch")
    if policy["schema"] != "nexara.qa-sidecar.policy.v1":
        raise Blocked("policy_schema_mismatch")
    if policy["repository"] != "Zsx154855/NEXARA-PRIME" or not SHA40.fullmatch(policy["commit_sha"]):
        raise Blocked("policy_repository_or_sha_invalid")
    counts = policy["expected_counts"]
    if not isinstance(counts, dict) or set(counts) != {"focused_passed", "full_passed", "subtests_passed"}:
        raise Blocked("policy_counts_invalid")
    if any(type(v) is not int or v < (0 if k == "subtests_passed" else 1) for k, v in counts.items()):
        raise Blocked("policy_counts_invalid")
    hashes = policy["expected_log_sha256"]
    if not isinstance(hashes, dict) or set(hashes) != {"focused.log", "full.log"}:
        raise Blocked("policy_hashes_invalid")
    if any(not isinstance(v, str) or not SHA256.fullmatch(v) for v in hashes.values()):
        raise Blocked("policy_hashes_invalid")
    signer = policy["signer"]
    if signer is not None and (
        not isinstance(signer, dict) or set(signer) != {"principal", "allowed_signers_sha256"}
        or not isinstance(signer["principal"], str) or not signer["principal"]
        or not isinstance(signer["allowed_signers_sha256"], str)
        or not SHA256.fullmatch(signer["allowed_signers_sha256"])
    ):
        raise Blocked("policy_signer_invalid")
    return policy


def assert_checkout(repo, policy):
    if not repo.is_dir() or repo.is_symlink():
        raise Blocked("invalid_repo")
    top = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    if top != repo:
        raise Blocked("wrong_repo_root")
    if git(repo, "rev-parse", "HEAD") != policy["commit_sha"]:
        raise Blocked("git_sha_mismatch")
    if git(repo, "status", "--porcelain", "--untracked-files=normal"):
        raise Blocked("git_dirty")
    origin = git(repo, "remote", "get-url", "origin")
    valid = {
        "https://github.com/Zsx154855/NEXARA-PRIME",
        "https://github.com/Zsx154855/NEXARA-PRIME.git",
        "git@github.com:Zsx154855/NEXARA-PRIME.git",
        "ssh://git@github.com/Zsx154855/NEXARA-PRIME.git",
    }
    if origin not in valid:
        raise Blocked("git_origin_mismatch")
    # Local origin config is not authenticated proof of GitHub upstream state.
    return origin


def assess(repo, evidence, policy, policy_digest):
    origin = assert_checkout(repo, policy)
    if evidence.is_symlink() or not evidence.is_dir():
        raise Blocked("invalid_evidence_dir")
    if evidence == repo or repo in evidence.parents:
        raise Blocked("evidence_not_external")
    chunks = {name: read_file(evidence / name) for name in FILES}
    if chunks["commit-sha.txt"].decode().strip() != policy["commit_sha"] or chunks["git-status.txt"].strip():
        raise Blocked("evidence_source_mismatch")
    expected = {
        "HEAD": policy["commit_sha"], "FOCUSED_EXIT": "0", "FULL_EXIT": "0",
        "WORKTREE_CLEAN": "YES", "REGRESSION": "PASS",
        "INDEPENDENT_QA": "NOT_VERIFIED", "PRODUCTION_LEARNING": "NOT_VERIFIED",
        "MODE": "MOCK_INTEGRATION",
    }
    fields = exact_fields(chunks["final-report.txt"].decode())
    for k, value in expected.items():
        if fields.get(k) != value:
            raise Blocked("final_report_mismatch:" + k)
    observed_sums = {}
    for line in chunks["log-sha256.txt"].decode().splitlines():
        match = HEXLOG.fullmatch(line)
        if not match:
            raise Blocked("invalid_hash_line")
        digest, original_path = match.groups()
        name = Path(original_path).name
        if name in observed_sums or name not in {"focused.log", "full.log"}:
            raise Blocked("hash_line_unknown_or_duplicate")
        # Basenames alone allow a forged log bundle from another directory.
        if Path(original_path).resolve() != (evidence / name).resolve():
            raise Blocked("hash_source_path_mismatch")
        observed_sums[name] = digest
    if set(observed_sums) != set(policy["expected_log_sha256"]):
        raise Blocked("missing_log_hash")
    for name, known in policy["expected_log_sha256"].items():
        current = sha256(chunks[name])
        if current != observed_sums[name] or current != known:
            raise Blocked("log_hash_mismatch:" + name)
    focused = re.findall(r"^\s*(\d+) passed in [\d.]+s\s*$", chunks["focused.log"].decode(), re.M)
    full = re.findall(r"^\s*(\d+) passed, (\d+) subtests passed in [\d.]+s\s*$", chunks["full.log"].decode(), re.M)
    if len(focused) != 1 or len(full) != 1:
        raise Blocked("pytest_summary_invalid")
    counts = {"focused_passed": int(focused[0]), "full_passed": int(full[0][0]),
              "subtests_passed": int(full[0][1])}
    if counts != policy["expected_counts"]:
        raise Blocked("pytest_counts_not_expected")
    return {
        "schema": "nexara.qa-sidecar.statement.v1",
        "repository": policy["repository"],
        "commit_sha": policy["commit_sha"],
        "policy_sha256": policy_digest,
        "git_origin_config": origin,
        "git_origin_authenticated": False,
        "pytest_counts": counts,
        "files_sha256": {name: sha256(chunks[name]) for name in sorted(chunks)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--statement-out", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--trusted-signers", type=Path)
    args = parser.parse_args()
    try:
        if args.repo.is_symlink() or args.evidence.is_symlink():
            raise Blocked("repo_or_evidence_symlink")
        repo, evidence = args.repo.resolve(), args.evidence.resolve()
        policy = load_policy(args.policy, args.policy_sha256, repo, evidence)
        statement = assess(repo, evidence, policy, args.policy_sha256)
        encoded = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
        if args.statement_out:
            output = args.statement_out
            if output.resolve() == repo or repo in output.resolve().parents or output.resolve() == evidence or evidence in output.resolve().parents:
                raise Blocked("output_not_external")
            with output.open("xb") as f:
                f.write(encoded)
        if bool(args.signature) != bool(args.trusted_signers):
            raise Blocked("signature_input_incomplete")
        signature = "ABSENT"
        if args.signature:
            signer = policy["signer"]
            if signer is None:
                raise Blocked("signature_not_authorized_by_policy")
            trust = args.trusted_signers
            if trust.resolve() == repo or repo in trust.resolve().parents or trust.resolve() == evidence or evidence in trust.resolve().parents:
                raise Blocked("trust_anchor_not_external")
            if sha256(read_file(trust)) != signer["allowed_signers_sha256"]:
                raise Blocked("trust_anchor_mismatch")
            signature_path = args.signature
            if signature_path.is_symlink() or not signature_path.is_file():
                raise Blocked("signature_missing")
            ssh = shutil.which("ssh-keygen")
            if not ssh:
                raise Blocked("ssh_keygen_missing")
            check = subprocess.run(
                [ssh, "-Y", "verify", "-f", str(trust), "-I", signer["principal"],
                 "-n", SIGN_NAMESPACE, "-s", str(signature_path)],
                input=encoded, capture_output=True, timeout=15, check=False,
            )
            if check.returncode:
                raise Blocked("signature_invalid")
            signature = "VALID_BUT_CUSTODY_UNVERIFIED"
        print(json.dumps({"technical": "PASS", "gate": "QA_BLOCKED",
                          "independent_identity": "NOT_VERIFIED", "signature": signature,
                          "statement_sha256": sha256(encoded),
                          "pytest_counts": statement["pytest_counts"]}, sort_keys=True))
        return 2
    except (Blocked, OSError, ValueError, UnicodeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"technical": "BLOCKED", "gate": "QA_BLOCKED",
                          "reason": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
