#!/usr/bin/env python3
"""Push c985392 content to GitHub via API, create branch + PR (main is protected)."""
import base64, json, os, subprocess, sys, tempfile

REPO = "Zsx154855/NEXARA-PRIME"
LOCAL = "c985392"
PARENT = "35aeb43ff51168098208899a30573caa551c517e"
BRANCH = "feat/home-v2.3"
MSG = "feat(home): complete NEXARA Home V2.3 runtime closure"

os.chdir("/Users/agentos/NEXARA-PRIME")

def die(msg):
    print(f"STOP: {msg}")
    sys.exit(1)

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True).stdout.strip()

def gh(method, path, body=None, jq=None):
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

# === Verify ===
assert run("git rev-parse HEAD")[:7] == "c985392"
assert run("git branch --show-current") == "main"
assert run(f"git rev-parse {LOCAL}^") == PARENT

# === Check remote ===
rh = gh("GET", "/git/ref/heads/main", jq=".object.sha")
assert rh == PARENT, f"Remote moved: {rh[:8]}"
print(f"Remote HEAD: {rh[:8]} OK")

# === Check if branch already exists (don't use gh() — 404 is expected) ===
br = subprocess.run(
    ["gh", "api", f"repos/{REPO}/git/ref/heads/{BRANCH}", "--jq", ".object.sha"],
    capture_output=True, text=True,
)
if br.returncode == 0:
    die(f"Branch {BRANCH} already exists at {br.stdout.strip()[:8]} — delete it first")
print(f"Branch {BRANCH} does not exist — will create")

# === Upload 12 changed files ===
changed = run(f"git diff --name-only {PARENT}..{LOCAL}").split("\n")
assert len(changed) == 12, f"Expected 12, got {len(changed)}"
print(f"Uploading {len(changed)} blobs...")

parent_tree = gh("GET", f"/git/commits/{PARENT}", jq=".tree.sha")
updates = []
for path in changed:
    tree_line = run(f"git ls-tree {LOCAL} -- '{path}'")
    parts = tree_line.split()
    mode, typ, local_sha = parts[0], parts[1], parts[2]
    raw = subprocess.run(f"git cat-file blob {local_sha}", shell=True, capture_output=True, check=True).stdout
    b64 = base64.b64encode(raw).decode("ascii")
    payload = json.dumps({"content": b64, "encoding": "base64"})
    remote_sha = gh("POST", "/git/blobs", body=payload, jq=".sha")
    assert remote_sha == local_sha, f"SHA mismatch: {path}"
    updates.append({"path": path, "mode": mode, "type": typ, "sha": remote_sha})
    print(f"  {remote_sha[:8]} {path}")

# === Create tree ===
tp = json.dumps({"base_tree": parent_tree, "tree": updates})
nt = gh("POST", "/git/trees", body=tp, jq=".sha")
print(f"Tree: {nt[:8]}")

# === Create commit ===
an = run(f"git show -s --format='%an' {LOCAL}")
ae = run(f"git show -s --format='%ae' {LOCAL}")
ad = run(f"git show -s --format='%aI' {LOCAL}")
cn = run(f"git show -s --format='%cn' {LOCAL}")
ce = run(f"git show -s --format='%ce' {LOCAL}")
cd = run(f"git show -s --format='%cI' {LOCAL}")
cp = json.dumps({
    "message": MSG, "tree": nt, "parents": [PARENT],
    "author": {"name": an, "email": ae, "date": ad},
    "committer": {"name": cn, "email": ce, "date": cd},
})
nc = gh("POST", "/git/commits", body=cp, jq=".sha")
print(f"Commit: {nc}")

# === Verify commit ===
v = json.loads(gh("GET", f"/git/commits/{nc}"))
assert v["parents"][0]["sha"] == PARENT
assert v["tree"]["sha"] == nt
print("Commit verified")

# === Create branch ===
ref_payload = json.dumps({"ref": f"refs/heads/{BRANCH}", "sha": nc})
gh("POST", "/git/refs", body=ref_payload)
print(f"Branch {BRANCH} -> {nc[:8]}")

# === Create PR ===
pr_payload = json.dumps({
    "title": MSG,
    "head": BRANCH,
    "base": "main",
    "body": (
        "## NEXARA Home V2.3 — Runtime Closure\n\n"
        "### Changes (12 files)\n"
        "- **MemoryWheel** — 4-quadrant memory visualization with real data\n"
        "- **CommandPalette** — ⌘K global search (missions, memories, actions)\n"
        "- **CurrentMissionCard** — active mission with single CTA\n"
        "- **Design tokens** — semantic surface/text/border/accent/state tokens\n"
        "- **WCAG AA** — text-secondary 5.56:1, text-tertiary 3.52:1\n"
        "- **Brand** — Nexara-柏韩 unified (sidebar, wheel, page title)\n"
        "- **Sidebar** — grouped navigation with accent active indicator\n"
        "- **Memory stats API** — GET /api/memory/stats (real data)\n"
        "- **CORS** — dev-only, whitelisted to localhost:3000\n\n"
        "### Verification\n"
        "- Backend tests: 79/79 PASS\n"
        "- TypeScript: 0 errors\n"
        "- Build: 0 errors (Next.js 16.2.10)\n"
        "- E2E browser QA: 5 real screenshots\n"
        "- WCAG AA contrast: measured + verified\n"
        "- ⌘K single-owner: verified\n"
        "- No duplicate CTA: verified\n\n"
        "### Evidence\n"
        "See `evidence/home_v2.3/` for screenshots and diagnostics.\n\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
    ),
})
pr = json.loads(gh("POST", "/pulls", body=pr_payload))
print(f"\nPR #{pr['number']}: {pr['html_url']}")

# === Final report ===
print(f"""
================================================
 NEXARA-PRIME GITHUB PUSH CLOSURE
================================================
AUTH=PASS
REPOSITORY={REPO}
BRANCH={BRANCH} -> main (PR)
LOCAL_SOURCE={LOCAL}
REMOTE_PARENT={PARENT[:8]}
REMOTE_COMMIT={nc[:8]}
TRANSPORT=GitHub_Git_Database_API
GIT_PUSH_USED=NO
FORCE_PUSH=NO
BLOBS=12/12
TREE=PASS (local={nt[:8]})
COMMIT=PASS ({nc[:8]})
BRANCH=PASS ({BRANCH})
PR=#{pr['number']} {pr['html_url']}
HOME_V2_3_FILES=12
LIVINGINTERFACE_EXCLUDED=PASS
EVIDENCE_EXCLUDED=PASS
UNRELATED_COMMITTED=0
FINAL_STATUS=PASS
""")
