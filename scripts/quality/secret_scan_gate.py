#!/usr/bin/env python3
"""Secret scan that fits the gate, without pretending.

Two modes:
  default      scan production paths that changed on this branch (fast, local)
  --full       run the repository scanner (slow; used by CI)

Test fixtures and docs are out of scope for the changed-file mode: a dummy
`token = "s3cret"` in a test is not a leaked credential, while a real one in
`src/` is. The full scanner still covers everything in CI.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scripts" / "security" / "scan_hardcoded_secrets.py"
PRODUCTION = ("src/", "platform/", "scripts/", "ui/src/")
EXCLUDE = ("scripts/security/", "scripts/quality/")
PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]([^'\"]{8,})['\"]"),
]
PLACEHOLDERS = ("test", "dummy", "example", "placeholder", "not-a-secret", "xxxx", "changeme", "<")


def changed_files() -> list[Path]:
    proc = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"],
                          capture_output=True, text=True, cwd=ROOT)
    names = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    out = []
    for name in names:
        if not name.startswith(PRODUCTION) or name.startswith(EXCLUDE):
            continue
        path = ROOT / name
        if path.exists() and path.stat().st_size < 2_000_000:
            out.append(path)
    return out


def scan_changed() -> list[str]:
    findings = []
    for path in changed_files():
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for pattern in PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(2).lower()
                if any(token in value for token in PLACEHOLDERS):
                    continue
                rel = path.relative_to(ROOT).as_posix()
                findings.append(f"{rel}:{number}: {match.group(1)} = <redacted>")
    return findings


def main() -> int:
    if "--full" in sys.argv:
        proc = subprocess.run([sys.executable, str(SCANNER)], cwd=ROOT)
        return proc.returncode
    findings = scan_changed()
    if not findings:
        print("secret scan: clean (changed production files)")
        return 0
    print(f"secret scan: {len(findings)} finding(s)")
    for item in findings:
        print("  " + item)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
