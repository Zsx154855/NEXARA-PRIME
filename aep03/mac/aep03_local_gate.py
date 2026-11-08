#!/usr/bin/env python3
"""AEP-03 one-shot Mac preflight, synthetic-code seeding and independent test receipts.

This program does not install software, launch OpenMausBot, run any AI model,
or remotely control a Mac. Its task directories must be fresh and disposable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

PR57 = "96d7628d69413a244d83bbe59ef143f5ab11a4bb"
PR58 = "f994e06a2c3897f4b7ca48ca4f71a281e06389c8"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def call(argv, cwd=None, timeout=30):
    try:
        p = subprocess.run(argv, cwd=cwd, text=True, capture_output=True,
                           timeout=timeout, check=False)
        return {"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"exit_code": 127, "stdout": "", "stderr": type(e).__name__}


def git(repo, *arguments):
    return call(["git", "-C", str(repo), *arguments], timeout=20)


def json_dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def probe(args):
    repo = Path(args.repo).expanduser().resolve()
    valid_repo = git(repo, "rev-parse", "--show-toplevel")
    head = git(repo, "rev-parse", "HEAD")
    branch = git(repo, "branch", "--show-current")
    dirty = git(repo, "status", "--porcelain=v1", "--untracked-files=normal")
    is_ancestor = git(repo, "merge-base", "--is-ancestor", PR57, PR58)
    repo_ok = valid_repo["exit_code"] == 0 and head["exit_code"] == 0
    binary = shutil.which(args.omb_binary)
    version = call([binary, "--version"], timeout=12) if binary else None
    doctor = call([binary, "doctor", "--json", "--url", args.omb_url], timeout=25) if binary else None
    try:
        details = json.loads(doctor["stdout"]) if doctor and doctor["stdout"] else None
    except json.JSONDecodeError:
        details = None
    # Strictly reduce doctor's output to non-sensitive booleans and counts.
    engine_list = details.get("availableEngines") if isinstance(details, dict) else None
    server = details.get("server") if isinstance(details, dict) else None
    result = {
        "kind": "AEP03_MAC_PREFLIGHT", "generated_at": timestamp(),
        "platform": {"system": platform.system(), "machine": platform.machine(),
                     "python": platform.python_version(), "sqlite": sqlite3.sqlite_version},
        "git": {"repo_available": repo_ok,
                "head": head["stdout"].strip() if head["exit_code"] == 0 else None,
                "branch": branch["stdout"].strip() if branch["exit_code"] == 0 else None,
                "dirty_entries": len(dirty["stdout"].splitlines()) if dirty["exit_code"] == 0 else None,
                "pr57_ancestor_of_pr58": is_ancestor["exit_code"] == 0,
                "pr57_object_available": git(repo, "cat-file", "-e", PR57)["exit_code"] == 0,
                "pr58_object_available": git(repo, "cat-file", "-e", PR58)["exit_code"] == 0},
        "openmausbot": {"cli_found": bool(binary),
                        "version": version["stdout"].strip()[:100] if version and version["exit_code"] == 0 else None,
                        "doctor_exit": doctor["exit_code"] if doctor else None,
                        "server_ready": bool(isinstance(details, dict) and details.get("ok") is True),
                        "server_version": (server.get("version") if isinstance(server, dict) else None),
                        "available_engine_count": len(engine_list) if isinstance(engine_list, list) else None,
                        "zero_incremental_cost_confirmed": False},
        "python_compatible": sys.version_info >= (3, 12),
        "pytest_installed": call([sys.executable, "-m", "pytest", "--version"], timeout=12)["exit_code"] == 0,
        "openminis_binary_found": bool(shutil.which("openminis")),
        "note": "No local executable was started except read-only Git/doctor/pytest-version checks."
    }
    result["status"] = "READY_FOR_MANUAL_COST_REVIEW" if (repo_ok and result["python_compatible"] and result["git"]["pr57_ancestor_of_pr58"] and result["openmausbot"]["server_ready"]) else "BLOCKED"
    json_dump(Path(args.out), result)
    print(json.dumps({"status": result["status"], "receipt": str(args.out),
                      "server_ready": result["openmausbot"]["server_ready"]}))
    return 0 if result["status"] == "READY_FOR_MANUAL_COST_REVIEW" else 3


CASES = {
    "task_a": {
        "module": '''def normalized_event_labels(raw: str) -> list[str]:\n    """Normalize comma-delimited event labels with stable order and no duplicates."""\n    return [piece.lower() for piece in raw.split(",") if piece]\n''',
        "tests": '''import unittest\nfrom canon import normalized_event_labels\n\nclass EventLabelTests(unittest.TestCase):\n    def test_trim_and_casefold(self):\n        self.assertEqual(normalized_event_labels(" Error ,SUCCESS, error "), ["error", "success"])\n    def test_ignore_empty_and_stable_order(self):\n        self.assertEqual(normalized_event_labels("Alpha,, BETA,alpha , gamma"), ["alpha", "beta", "gamma"])\n    def test_unicode_casefold(self):\n        self.assertEqual(normalized_event_labels(" STRASSE , Straße "), ["strasse"])\n''',
        "brief": "TASK A: Diagnose and fix the failing label canonicalization tests. Researcher must document the cause; Engineer modifies only src/canon.py; Auditor independently executes the same tests and writes a fresh log and report. No paid calls or unrelated files."
    },
    "task_b_control": {
        "module": '''def normalized_skill_codes(raw: str) -> list[str]:\n    """Normalize pipe-delimited skill codes with stable order and no duplicates."""\n    return [piece.lower() for piece in raw.split("|") if piece]\n''',
        "tests": '''import unittest\nfrom canon import normalized_skill_codes\n\nclass SkillCodeTests(unittest.TestCase):\n    def test_trim_and_casefold(self):\n        self.assertEqual(normalized_skill_codes(" WRITE |Read| write "), ["write", "read"])\n    def test_empty_and_stable_order(self):\n        self.assertEqual(normalized_skill_codes("Build|| TEST |build| audit"), ["build", "test", "audit"])\n    def test_unicode(self):\n        self.assertEqual(normalized_skill_codes(" STRASSE | Straße "), ["strasse"])\n''',
        "brief": "TASK B CONTROL: Fix this different pipe-delimited skill code bug without loading task A experience. Record tests, tool calls and tokens."
    },
}
CASES["task_b_memory"] = {
    **CASES["task_b_control"],
    "brief": "TASK B MEMORY: Fix this different pipe-delimited skill code bug. First retrieve task A's VERIFIED experience from NEXARA's real cognitive-memory interface; cite its entry ID; judge applicability and apply only if relevant. Record tests, tool calls and tokens."
}


def seed(args):
    root = Path(args.root).expanduser().absolute()
    if root.exists():
        raise ValueError("refuse_existing_lab_directory")
    root.mkdir(parents=True)
    for name, case in CASES.items():
        base = root / name
        (base / "src").mkdir(parents=True)
        (base / "tests").mkdir(parents=True)
        (base / "src" / "canon.py").write_text(case["module"], encoding="utf-8")
        (base / "tests" / "test_canon.py").write_text(case["tests"], encoding="utf-8")
        (base / "TASK.md").write_text(case["brief"] + "\n", encoding="utf-8")
        init = call(["git", "init", "-q", "-b", "main"], cwd=base)
        if init["exit_code"] != 0:
            raise RuntimeError("git_init_failed")
        stage = call(["git", "add", "src/canon.py", "tests/test_canon.py", "TASK.md"], cwd=base)
        commit = call(["git", "-c", "user.name=AEP Lab", "-c", "user.email=lab@example.invalid",
                       "commit", "-qm", "Baseline: intentionally failing synthetic normalization"], cwd=base)
        if stage["exit_code"] != 0 or commit["exit_code"] != 0:
            raise RuntimeError("baseline_commit_failed")
    manifest = {"kind": "AEP03_SYNTHETIC_LAB", "created_at": timestamp(),
                "tasks": {name: {"baseline_commit": git(root / name, "rev-parse", "HEAD")["stdout"].strip(),
                                 "tests_command": "PYTHONPATH=src python -m unittest discover -s tests -v",
                                 "test_sha256": digest((root / name / "tests" / "test_canon.py").read_bytes()),
                                 "is_synthetic": True} for name in CASES}}
    json_dump(root / "lab_manifest.json", manifest)
    print(json.dumps({"created": str(root), "tasks": list(CASES)}))
    return 0


def verify(args):
    project = Path(args.project).expanduser().resolve()
    if not (project / "src" / "canon.py").is_file() or not (project / "tests" / "test_canon.py").is_file():
        raise ValueError("invalid_synthetic_project")
    out = Path(args.out).expanduser().absolute()
    if out.exists():
        raise ValueError("refuse_overwrite_existing_receipt")
    manifest_path = project.parent / "lab_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("missing_original_lab_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_tests = manifest.get("tasks", {}).get(project.name, {}).get("test_sha256")
    if digest((project / "tests" / "test_canon.py").read_bytes()) != expected_tests:
        raise ValueError("tests_modified_since_synthetic_baseline")
    # Keep credential-bearing environment variables out of code executed by
    # independent OS subprocesses; this is NOT a kernel security sandbox.
    isolated_home = out.parent / "isolated-home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": str(isolated_home), "TMPDIR": str(isolated_home),
           "PYTHONPATH": str(project / "src"), "PYTHONNOUSERSITE": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                       cwd=project, env=env, text=True, capture_output=True, timeout=45, check=False)
    raw = (p.stdout + "\n" + p.stderr).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    logfile = out.with_suffix(".log")
    if logfile.exists():
        raise ValueError("refuse_overwrite_existing_log")
    logfile.write_bytes(raw)
    diff = git(project, "diff", "--binary", "HEAD", "--", "src/canon.py", "tests/test_canon.py")
    result = {"kind": "AEP03_OS_INDEPENDENT_TEST", "timestamp": timestamp(),
              "phase": args.phase, "status": "PASS" if p.returncode == 0 else "FAIL",
              "test_exit_code": p.returncode,
              "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
              "log_sha256": digest(raw), "log_filename": logfile.name,
              "source_sha256": digest((project / "src" / "canon.py").read_bytes()),
              "test_sha256": digest((project / "tests" / "test_canon.py").read_bytes()),
              "patch_sha256": digest(diff["stdout"].encode()),
              "git_head": git(project, "rev-parse", "HEAD")["stdout"].strip(),
              "separate_test_subprocess": True, "operating_system_sandbox_verified": False,
              "qa_verified": False, "actual_agent_or_openmausbot_proven": False,
              "warning": "An OS test receipt alone does not establish which Agent authored or reviewed the patch."}
    json_dump(out, result)
    print(json.dumps({"phase": args.phase, "status": result["status"], "exit_code": p.returncode,
                      "receipt": str(out)}))
    return 0 if p.returncode == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    p = sub.add_parser("probe", help="read-only Mac Git and actual OpenMausBot doctor check")
    p.add_argument("--repo", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--omb-url", default="http://127.0.0.1:8799")
    p.add_argument("--omb-binary", default="openmausbot")
    p.set_defaults(func=probe)
    p = sub.add_parser("seed", help="create three disposable, real failing-code repositories")
    p.add_argument("--root", required=True)
    p.set_defaults(func=seed)
    p = sub.add_parser("verify", help="run a real OS subprocess to verify a synthetic repo")
    p.add_argument("--project", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--phase", choices=("baseline", "post", "qa", "transfer"), required=True)
    p.set_defaults(func=verify)
    args = ap.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
        print(json.dumps({"ok": False, "reason": str(e), "kind": type(e).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
