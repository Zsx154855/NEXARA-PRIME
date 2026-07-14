#!/usr/bin/env python3
"""NEXARA PRIME — Hardcoded Secret Scanner.

Scans source files for hardcoded credentials. Detects both single-quoted and
double-quoted patterns. Excludes fixtures, examples, env lookups, and
explicitly allowed placeholder values.

Exit: 0 = clean, 1 = secrets found, 2 = config error.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Patterns to detect ──
SECRET_KEYS = (
    "api_key", "secret_key", "private_key", "password", "token",
    "access_token", "api_token", "client_secret", "signing_key",
)

# Regex: SECRET_KEY = "value" or SECRET_KEY = 'value'
# Handles nesting variations: env vars, f-strings, dict access
_DQ_PATTERN = re.compile(
    r'(?:^|[^.\w])(' + "|".join(SECRET_KEYS) + r')\s*[:=]\s*"([^"]{6,})"',
    re.IGNORECASE,
)
_SQ_PATTERN = re.compile(
    r'(?:^|[^.\w])(' + "|".join(SECRET_KEYS) + r")\s*[:=]\s*'([^']{6,})'",
    re.IGNORECASE,
)

# ── Allowed patterns (not secrets) ──
ALLOWED_PATTERNS = (
    r'os\.(environ|getenv)\b',             # env var lookup
    r'\$\{?[A-Z_]',                         # ${VAR} or $VAR reference
    r'\.env\.',                             # dotenv reference
    r'example|dummy|test|placeholder|mock|sample|your-',  # test/examples
    r'<.*>',                                # template placeholder
    r'changeme|replaceme|fill-in',          # explicit placeholders
    r'_PLACEHOLDER_|_TOKEN_',              # placeholder markers
    r'\bfixture\b',                         # fixture
    r'my-secret|my-key|test-key|sk-abc|ghp_1',  # test fixture values
    r'BEGIN.*PRIVATE KEY',                 # PEM markers in tests
    r'(Token|token):\s*["\']#[0-9a-fA-F]{6}',  # pygments color tokens
)

# ── File extensions to scan ──
EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".swift", ".yaml", ".yml", ".json", ".sh", ".toml"}

# ── Directories to skip ──
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules", ".build", "DerivedData", ".obsidian", "dist", "Chats"}
SKIP_DIR_PREFIXES = (".venv",)  # matches .venv, .venv.backup, .venv.backup.20260714-051419, etc.


def is_allowed(line: str) -> bool:
    """Return True if the line matches an allowed (non-secret) pattern."""
    return any(re.search(p, line, re.IGNORECASE) for p in ALLOWED_PATTERNS)


def scan_file(path: Path) -> list[dict]:
    """Scan a single file. Returns list of findings."""
    findings = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern in (_DQ_PATTERN, _SQ_PATTERN):
            for match in pattern.finditer(line):
                full = match.group(0)
                if not is_allowed(full):
                    try:
                        rel = str(path.relative_to(REPO_ROOT))
                    except ValueError:
                        rel = str(path)
                    findings.append({
                        "file": rel,
                        "line": lineno,
                        "key": match.group(1),
                        "match": full.strip()[:120],
                        "quote": '"' if '"' in full else "'",
                    })
    return findings


def scan_repo(root: Path) -> list[dict]:
    """Scan entire repo for hardcoded secrets."""
    all_findings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS or part.startswith(SKIP_DIR_PREFIXES) for part in path.parts):
            continue
        if path.suffix.lower() not in EXTENSIONS:
            continue
        all_findings.extend(scan_file(path))
    return all_findings


def main() -> int:
    findings = scan_repo(REPO_ROOT)
    if not findings:
        print("Secret scan: CLEAN — no hardcoded secrets detected")
        return 0

    print(f"Secret scan: FAILED — {len(findings)} finding(s)")
    for f in findings:
        print(f"  {f['file']}:{f['line']}  {f['key']} = {f['quote']}...{f['quote']}")
        print(f"    → {f['match']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
