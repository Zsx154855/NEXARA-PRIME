"""Build immutable qualification artifact manifest from frozen commit.

All file content and hashes are read from the GIT COMMIT, not the working tree.
Same input -> same output, byte-for-byte.
All CI provenance must be explicit — no hardcoded defaults.

Usage:
  python build_artifact_manifest.py --repo <path> --subject-head <SHA> \
      --ci-run <run_id> --ci-head <SHA> --ci-conclusion success \
      --output <path>
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(msg: str) -> None:
    print("FAIL: {}".format(msg), file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path, timeout: int = 30) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        fail("{} -> {}".format(" ".join(cmd), r.stderr.strip()[:200]))
    return r.stdout


def git_show(repo: Path, commit: str, path: str) -> bytes:
    r = subprocess.run(
        ["git", "show", "{}:{}".format(commit, path)],
        cwd=repo, capture_output=True, timeout=30,
    )
    if r.returncode != 0:
        fail("MISSING: {} not found in commit {}".format(path, commit[:12]))
    return r.stdout


def git_blob(repo: Path, commit: str, path: str) -> str:
    r = subprocess.run(
        ["git", "ls-tree", commit, path],
        cwd=repo, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        fail("FAIL: git ls-tree {} {} returned empty".format(commit[:12], path))
    parts = r.stdout.strip().split()
    blob = parts[2]
    if not blob or len(blob) != 40:
        fail("FAIL: invalid git_blob_sha for {}: {}".format(path, blob))
    return blob


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ═══ Validation ═══

def validate_full_sha(value: str, field_name: str) -> str:
    v = value.strip().lower()
    if not v:
        fail("{} must not be empty".format(field_name))
    if not SHA_RE.match(v):
        fail("{} must be a full 40-char hex SHA, got: {}".format(field_name, v[:50]))
    return v


def validate_reachable(repo: Path, sha: str, field_name: str) -> None:
    r = subprocess.run(["git", "cat-file", "-e", "{}^{{commit}}".format(sha)],
                       cwd=repo, capture_output=True, timeout=10)
    if r.returncode != 0:
        fail("{} {} is not a reachable commit in {}".format(field_name, sha[:12], repo))


def validate_ci_run(value: str) -> int:
    v = value.strip()
    if not v:
        fail("--ci-run must not be empty")
    try:
        n = int(v)
    except ValueError:
        fail("--ci-run must be a positive integer, got: {}".format(v))
    if n <= 0:
        fail("--ci-run must be > 0, got: {}".format(n))
    return n


def validate_ci_conclusion(value: str) -> str:
    v = value.strip().lower()
    if v != "success":
        fail("--ci-conclusion must be 'success', got: '{}'".format(v))
    return v


def validate_subject_matches_ci(subject: str, ci_head: str) -> None:
    if subject != ci_head:
        fail("ci-head ({}) must equal subject-head ({})".format(ci_head[:12], subject[:12]))


def validate_repo(repo: Path) -> None:
    if not (repo / ".git").exists():
        fail("{} is not a git repository".format(repo))


def validate_output_path(repo: Path, output: Path) -> None:
    """Output must be within repo or a temp/test directory."""
    op = output.resolve()
    try:
        op.relative_to(repo.resolve())
        return  # inside repo: OK
    except ValueError:
        pass
    # Allow /tmp for testing
    if "/tmp/" in str(op) or "/var/folders/" in str(op):
        return
    fail("output path must be within repository or temp directory: {}".format(output))


# ═══ Main ═══

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path to git repository")
    ap.add_argument("--subject-head", required=True, help="Frozen commit SHA (full 40-char)")
    ap.add_argument("--ci-run", required=True, help="CI run ID (positive integer)")
    ap.add_argument("--ci-head", required=True, help="CI verified commit SHA (full 40-char)")
    ap.add_argument("--ci-conclusion", required=True, help="CI conclusion (must be 'success')")
    ap.add_argument("--output", required=True, help="Output manifest path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    output_path = Path(args.output).resolve()

    # Validate all inputs
    validate_repo(repo)
    validate_output_path(repo, output_path)

    subject_head = validate_full_sha(args.subject_head, "--subject-head")
    ci_head = validate_full_sha(args.ci_head, "--ci-head")
    ci_run = validate_ci_run(args.ci_run)
    ci_conclusion = validate_ci_conclusion(args.ci_conclusion)

    validate_reachable(repo, subject_head, "--subject-head")
    validate_reachable(repo, ci_head, "--ci-head")
    validate_subject_matches_ci(subject_head, ci_head)

    # Subject tree and timestamp
    tree = run(["git", "show", "-s", "--format=%T", subject_head], repo).strip()
    ts = run(["git", "show", "-s", "--format=%aI", subject_head], repo).strip()

    # Enumerate files from frozen commit
    all_files = run(["git", "ls-tree", "-r", "--name-only", subject_head], repo).strip().split("\n")

    required_gov = [
        "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md",
        "governance/nsec.yaml",
        "governance/authority_index.yaml",
        "NEXARA_DEVELOPMENT_GATES_V1.yaml",
    ]
    for rg in required_gov:
        if rg not in all_files:
            fail("required governance file missing: {}".format(rg))

    categories = {"governance": [], "contract": [], "source": [], "test": [], "evidence": []}
    for f in all_files:
        if f in required_gov:
            categories["governance"].append(f)
        elif f.startswith(".nexara/contracts/") and f.endswith(".yaml"):
            categories["contract"].append(f)
        elif f.startswith("src/nexara_prime/") and f.endswith(".py"):
            categories["source"].append(f)
        elif f.startswith("tests/") and f.endswith(".py") and "test_" in Path(f).name:
            categories["test"].append(f)
        elif f.startswith(".nexara/evidence/") and (f.endswith(".md") or f.endswith(".json")):
            categories["evidence"].append(f)

    artifacts = []
    cat_counts = {}
    for category in ["governance", "contract", "source", "test", "evidence"]:
        for f in sorted(categories[category]):
            content = git_show(repo, subject_head, f)
            blob = git_blob(repo, subject_head, f)
            artifacts.append({
                "path": f, "git_blob_sha": blob, "sha256": sha256(content), "category": category,
            })
        cat_counts[category] = len(categories[category])

    manifest = {
        "schema_version": "1.0",
        "qualification_subject_head": subject_head,
        "qualification_subject_tree": tree,
        "ci": {
            "run_id": ci_run,
            "head_sha": ci_head,
            "conclusion": ci_conclusion,
        },
        "subject_commit_timestamp": ts,
        "collection_method": "git show {}:<path>".format(subject_head),
        "artifacts": artifacts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output_path.write_text(out, encoding="utf-8")

    print("subject_head: {}".format(subject_head))
    print("subject_tree: {}".format(tree))
    print("ci_run: {}".format(ci_run))
    print("ci_head: {}".format(ci_head))
    print("ci_conclusion: {}".format(ci_conclusion))
    print("artifact_count: {}".format(len(artifacts)))
    print("category_counts: {}".format(json.dumps(cat_counts)))
    print("output_sha256: {}".format(sha256(output_path.read_bytes())))
    print("output_size_bytes: {}".format(output_path.stat().st_size))

    return 0


if __name__ == "__main__":
    sys.exit(main())
