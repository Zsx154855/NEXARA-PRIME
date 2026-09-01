#!/usr/bin/env python3
"""Create branch + PR for the API-pushed commit 51d0ae9a."""
import json, os, subprocess, sys

REPO = "Zsx154855/NEXARA-PRIME"
REMOTE_COMMIT = "51d0ae9ab1c9f0c7a0e2c1c4d15336e0889f1cf0"  # from api_push.py output
PARENT = "35aeb43ff51168098208899a30573caa551c517e"

os.chdir("/Users/agentos/NEXARA-PRIME")

def die(msg):
    print(f"FAIL: {msg}"); sys.exit(1)

def gh(method, path, body=None, jq=None):
    import tempfile
    tmpf = None
    if body is not None:
        tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmpf.write(body)
        tmpf.close()
    args = ["gh", "api", "--method", method, f"repos/{REPO}{path}"]
    if jq: args += ["--jq", jq]
    if tmpf: args += ["--input", tmpf.name]
    r = subprocess.run(args, capture_output=True, text=True)
    if tmpf: os.unlink(tmpf.name)
    if r.returncode != 0:
        die(f"GH {method} {path}: {r.stderr.strip()}")
    return r.stdout.strip()

# Step 1: Verify remote commit exists
v = json.loads(gh("GET", f"/git/commits/{REMOTE_COMMIT}"))
assert v["parents"][0]["sha"] == PARENT
print(f"Remote commit {REMOTE_COMMIT[:8]} verified")

# Step 2: Create branch 'feat/home-v2.3' pointing to remote commit
ref_payload = json.dumps({
    "ref": "refs/heads/feat/home-v2.3",
    "sha": REMOTE_COMMIT,
})
gh("POST", "/git/refs", body=ref_payload)
print("Branch feat/home-v2.3 created")

# Step 3: Create PR
pr_payload = json.dumps({
    "title": "feat(home): complete NEXARA Home V2.3 runtime closure",
    "head": "feat/home-v2.3",
    "base": "main",
    "body": (
        "## NEXARA Home V2.3 — Runtime Closure\n\n"
        "### Changes (12 files)\n"
        "- MemoryWheel — 4-quadrant memory visualization\n"
        "- CommandPalette — ⌘K global search\n"
        "- CurrentMissionCard — active mission with single CTA\n"
        "- Design tokens — semantic surface/text/border/accent tokens\n"
        "- WCAG AA contrast — text-secondary 5.56:1, text-tertiary 3.52:1\n"
        "- Brand — Nexara-柏韩 unified\n"
        "- Sidebar — grouped navigation with active indicator\n"
        "- Memory stats API — GET /api/memory/stats\n"
        "- CORS middleware — dev-only, whitelisted to localhost:3000\n"
        "- configureApi — client-side dev/prod base URL\n\n"
        "### Verification\n"
        "- Backend tests: 79/79 PASS\n"
        "- TypeScript: 0 errors\n"
        "- Build: 0 errors\n"
        "- E2E browser QA: 5 real screenshots\n\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
    ),
})
pr = json.loads(gh("POST", "/pulls", body=pr_payload))
pr_num = pr["number"]
pr_url = pr["html_url"]
print(f"PR #{pr_num} created: {pr_url}")

# Verify PR
pr_check = json.loads(gh("GET", f"/pulls/{pr_num}"))
print(f"PR state: {pr_check['state']}, mergeable: {pr_check.get('mergeable', 'unknown')}")
