"""Build immutable qualification artifact manifest from frozen commit.

All file content and hashes are read from the GIT COMMIT, not the working tree.
Same input -> same output, byte-for-byte.

Usage:
  python build_artifact_manifest_v3.py --repo <path> --subject-head <SHA> --output <path>
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path, timeout: int = 30) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print("FAIL: {} -> {}".format(" ".join(cmd), r.stderr.strip()[:200]), file=sys.stderr)
        sys.exit(1)
    return r.stdout


def git_show(repo: Path, commit: str, path: str) -> bytes:
    r = subprocess.run(
        ["git", "show", "{}:{}".format(commit, path)],
        cwd=repo, capture_output=True, timeout=30,
    )
    if r.returncode != 0:
        print("MISSING: {} not found in commit {}".format(path, commit[:12]), file=sys.stderr)
        sys.exit(1)
    return r.stdout


def git_blob(repo: Path, commit: str, path: str) -> str:
    r = subprocess.run(
        ["git", "ls-tree", commit, path],
        cwd=repo, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        print("FAIL: git ls-tree {} {} returned empty".format(commit[:12], path), file=sys.stderr)
        sys.exit(1)
    parts = r.stdout.strip().split()
    blob = parts[2]
    if not blob or len(blob) != 40:
        print("FAIL: invalid git_blob_sha for {}: {}".format(path, blob), file=sys.stderr)
        sys.exit(1)
    return blob


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path to git repository")
    ap.add_argument("--subject-head", required=True, help="Frozen commit SHA")
    ap.add_argument("--output", required=True, help="Output manifest path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    subject_head = args.subject_head
    output_path = Path(args.output).resolve()

    if not (repo / ".git").exists():
        print("FAIL: {} is not a git repository".format(repo), file=sys.stderr)
        sys.exit(1)

    tree = run(["git", "show", "-s", "--format=%T", subject_head], repo).strip()
    ts = run(["git", "show", "-s", "--format=%aI", subject_head], repo).strip()
    all_files = run(["git", "ls-tree", "-r", "--name-only", subject_head], repo).strip().split("\n")

    required_gov = [
        "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md",
        "governance/nsec.yaml",
        "governance/authority_index.yaml",
        "NEXARA_DEVELOPMENT_GATES_V1.yaml",
    ]
    for rg in required_gov:
        if rg not in all_files:
            print("FAIL: required governance file missing: {}".format(rg), file=sys.stderr)
            sys.exit(1)

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
                "path": f,
                "git_blob_sha": blob,
                "sha256": sha256(content),
                "category": category,
            })
        cat_counts[category] = len(categories[category])

    manifest = {
        "schema_version": "1.0",
        "qualification_subject_head": subject_head,
        "qualification_subject_tree": tree,
        "ci_run": "30057162252",
        "ci_head": subject_head,
        "ci_conclusion": "success",
        "subject_commit_timestamp": ts,
        "collection_method": "git show {}:<path>".format(subject_head),
        "artifacts": artifacts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output_path.write_text(out, encoding="utf-8")

    print("subject_head: {}".format(subject_head))
    print("subject_tree: {}".format(tree))
    print("subject_timestamp: {}".format(ts))
    print("artifact_count: {}".format(len(artifacts)))
    print("category_counts: {}".format(json.dumps(cat_counts)))
    print("missing_required_files: 0")
    print("output_sha256: {}".format(sha256(output_path.read_bytes())))
    print("output_size_bytes: {}".format(output_path.stat().st_size))

    return 0


if __name__ == "__main__":
    sys.exit(main())
