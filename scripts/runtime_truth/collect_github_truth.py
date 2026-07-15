"""Collect PR truth from GitHub API. Never hand-write PR metadata."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone


def _gh_api(query: str) -> dict:
    """Run a gh api command and return parsed JSON."""
    result = subprocess.run(
        ["gh", "api", query],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr}")
    return json.loads(result.stdout)


def _gh_graphql(query: str) -> dict:
    """Run a gh api graphql query and return parsed JSON."""
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh graphql failed: {result.stderr}")
    data = json.loads(result.stdout)
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data


def collect_pr_truth(pr_number: int) -> dict:
    """Return canonical PR truth from GitHub.

    Returns:
        {pr_number, state, mergedAt, mergeCommit, headRefOid, baseRefOid,
         unresolved_threads, gitguardian_status}
    """
    query = (
        f"query {{ repository(owner: \"Zsx154855\", name: \"NEXARA-PRIME\") {{"
        f"  pullRequest(number: {pr_number}) {{"
        f"    state mergedAt headRefOid baseRefOid"
        f"    mergeCommit {{ oid }}"
        f"    reviewThreads(first: 50) {{ totalCount nodes {{ isResolved isOutdated }} }}"
        f"  }} }} }}"
    )
    data = _gh_graphql(query)
    pr = data["data"]["repository"]["pullRequest"]
    threads = pr["reviewThreads"]
    unresolved = sum(
        1 for n in threads["nodes"]
        if not n["isResolved"] and not n["isOutdated"]
    )

    # Parse ISO timestamp to datetime
    merged_dt = None
    if pr.get("mergedAt"):
        merged_dt = datetime.fromisoformat(pr["mergedAt"])

    return {
        "pr_number": pr_number,
        "state": pr["state"],
        "merged_at_utc": merged_dt.isoformat().replace("+00:00", "Z") if merged_dt else None,
        "merged_at_dt": merged_dt,
        "merge_commit": pr.get("mergeCommit", {}).get("oid") if pr.get("mergeCommit") else None,
        "head_sha": pr["headRefOid"],
        "base_sha": pr["baseRefOid"],
        "unresolved_threads": unresolved,
    }


def collect_gitguardian_status(pr_number: int) -> str:
    """Return GitGuardian status: 'PASS', 'FAIL', or 'UNKNOWN'."""
    try:
        result = subprocess.run(
            ["gh", "pr", "checks", str(pr_number)],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.splitlines():
            if "GitGuardian" in line:
                if "pass" in line.lower():
                    return "PASS"
                elif "fail" in line.lower():
                    return "FAIL"
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def collect_all_pr_truth(pr_numbers: list[int]) -> dict:
    """Collect truth for multiple PRs, returning a merged truth dict."""
    result = {}
    for n in pr_numbers:
        result[str(n)] = collect_pr_truth(n)
    return result


if __name__ == "__main__":
    prs = [int(a) for a in sys.argv[1:]] if sys.argv[1:] else [8, 10, 11]
    truth = collect_all_pr_truth(prs)
    print(json.dumps(truth, indent=2, default=str))
