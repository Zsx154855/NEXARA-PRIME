#!/usr/bin/env python3
"""NEXARA PRIME — Hardcoded Secret Scanner.

Scans source and configuration files for literal credentials. The scanner is
fail-closed for common secret-bearing variable names, including provider- or
service-prefixed names such as ``openai_api_key`` and ``github_token``.

Exit codes:
    0 — clean
    1 — one or more probable hardcoded secrets found
    2 — scanner configuration/runtime error
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Longest/specific suffixes first. A secret-bearing identifier may be the exact
# suffix (``api_key``) or a prefixed identifier (``openai_api_key``).
SECRET_KEYS = (
    "access_token",
    "client_secret",
    "private_key",
    "secret_key",
    "signing_key",
    "api_token",
    "api_key",
    "password",
    "token",
)
_SECRET_SUFFIX = "(?:" + "|".join(re.escape(key) for key in SECRET_KEYS) + ")"
_SECRET_IDENTIFIER = (
    r"((?:[A-Za-z_][A-Za-z0-9_]*_)?" + _SECRET_SUFFIX + r")"
)

# Match assignments and mapping entries using either quote style. The negative
# lookbehind prevents matching attribute reads such as ``client.api_key``.
_DQ_PATTERN = re.compile(
    r"(?<![.\w])" + _SECRET_IDENTIFIER + r'\s*[:=]\s*"([^"]{6,})"',
    re.IGNORECASE,
)
_SQ_PATTERN = re.compile(
    r"(?<![.\w])" + _SECRET_IDENTIFIER + r"\s*[:=]\s*'([^']{6,})'",
    re.IGNORECASE,
)

# Quoted-key patterns (JSON, Python/TS dict, object literal)
_QUOTED_KEY_DQ = re.compile(
    r'["\'](' + _SECRET_IDENTIFIER + r')["\']\s*:\s*"([^"]{6,})"',
    re.IGNORECASE,
)
_QUOTED_KEY_SQ = re.compile(
    r'["\'](' + _SECRET_IDENTIFIER + r')["\']\s*:\s*\'([^\']{6,})\'',
    re.IGNORECASE,
)

# Attribute assignment pattern: settings.api_key = "value"
_ATTR_DQ = re.compile(
    r'\.(' + _SECRET_IDENTIFIER + r')\s*=\s*"([^"]{6,})"',
    re.IGNORECASE,
)
_ATTR_SQ = re.compile(
    r'\.(' + _SECRET_IDENTIFIER + r')\s*=\s*\'([^\']{6,})\'',
    re.IGNORECASE,
)

# Dict subscript pattern: config["api_key"] = "value"
_SUBSCRIPT_DQ = re.compile(
    r'\[["\'](' + _SECRET_IDENTIFIER + r')["\']\]\s*=\s*"([^"]{6,})"',
    re.IGNORECASE,
)
_SUBSCRIPT_SQ = re.compile(
    r'\[["\'](' + _SECRET_IDENTIFIER + r')["\']\]\s*=\s*\'([^\']{6,})\'',
    re.IGNORECASE,
)
# PEM private key detection (multi-line support: match the BEGIN line)
# Key assignment followed by BEGIN PRIVATE KEY (closing quote may be on later line)
_PEM_ASSIGN_DQ = re.compile(
    r"(?<![.\w])" + _SECRET_IDENTIFIER + r'\s*[:=]\s*"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|ENCRYPTED)\s+PRIVATE\s+KEY-----',
    re.IGNORECASE,
)
_PEM_ASSIGN_SQ = re.compile(
    r"(?<![.\w])" + _SECRET_IDENTIFIER + r"\s*[:=]\s*'-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|ENCRYPTED)\s+PRIVATE\s+KEY-----",
    re.IGNORECASE,
)


# Explicit non-secret forms. Keep these narrow: broad words such as ``test``
# must not suppress a real credential merely because it appears in a test file.
ALLOWED_PATTERNS = (
    r"os\.(environ|getenv)\b",              # environment lookup
    r"\$\{?[A-Z_][A-Z0-9_]*\}?",           # ${VAR} or $VAR reference
    r"\.env\b",                            # dotenv reference
    r"[:=]\s*[\"'][^\"']*(?:example|dummy|placeholder|mock|sample|your-)",
    r"[:=]\s*[\"'][^\"']*(?:changeme|replaceme|fill-in)",
    r"[:=]\s*[\"'][^\"']*(?:my-secret|my-key|test-key|sk-abc)",
    r"<[^>]+>",                             # template placeholder
    r"_PLACEHOLDER_|_TOKEN_",               # explicit markers
    # PEM headers are only allowed in explicit test-fixture comments
    r"#\s*fixture|#\s*test[-_]data|#\s*NEXARA[-_]TEST",
    r"(?:Token|token):\s*[\"']#[0-9a-fA-F]{6}",  # colour token
)

EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".swift",
    ".yaml",
    ".yml",
    ".json",
    ".sh",
    ".toml",
}

SKIP_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".build",
    "DerivedData",
    ".obsidian",
    "dist",
    "Chats",
}
SKIP_DIR_PREFIXES = (".venv",)


def is_allowed(line: str) -> bool:
    """Return True when a line is an explicit non-secret placeholder/reference."""

    return any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWED_PATTERNS)


def is_self_referential(match: re.Match) -> bool:
    """Return True when the matched value equals the key name (enum self-reference)."""
    key_name = match.group(1)
    matched_text = match.group(0).strip().rstrip(",")
    variants = {
        f'{key_name} = "{key_name}"',
        f"{key_name} = '{key_name}'",
        f'{key_name}: "{key_name}"',
        f"{key_name}: '{key_name}'",
        f'"{key_name}": "{key_name}"',
        f"'{key_name}': '{key_name}'",
    }
    return matched_text in variants


def scan_file(path: Path) -> list[dict[str, object]]:
    """Scan one file and return normalized findings."""

    findings: list[dict[str, object]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    for lineno, line in enumerate(content.splitlines(), 1):
        all_patterns = [
            (_DQ_PATTERN, '"'), (_SQ_PATTERN, "'"),
            (_QUOTED_KEY_DQ, '"'), (_QUOTED_KEY_SQ, "'"),
            (_ATTR_DQ, '"'), (_ATTR_SQ, "'"),
            (_SUBSCRIPT_DQ, '"'), (_SUBSCRIPT_SQ, "'"),
            (_PEM_ASSIGN_DQ, '"'), (_PEM_ASSIGN_SQ, "'"),
        ]
        for pattern, quote in all_patterns:
            for match in pattern.finditer(line):
                if is_allowed(line):
                    continue
                if is_self_referential(match):
                    continue
                try:
                    rel = str(path.relative_to(REPO_ROOT))
                except ValueError:
                    rel = str(path)
                findings.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "key": match.group(1),
                        "match": match.group(0).strip()[:120],
                        "quote": quote,
                    }
                )
    return findings


def scan_repo(root: Path) -> list[dict[str, object]]:
    """Recursively scan supported files below ``root``."""

    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(
            part in SKIP_DIRS or part.startswith(SKIP_DIR_PREFIXES)
            for part in path.parts
        ):
            continue
        if path.suffix.lower() not in EXTENSIONS:
            continue
        findings.extend(scan_file(path))
    return findings


def main() -> int:
    findings = scan_repo(REPO_ROOT)
    if not findings:
        print("Secret scan: CLEAN — no hardcoded secrets detected")
        return 0

    print(f"Secret scan: FAILED — {len(findings)} finding(s)")
    for finding in findings:
        quote = finding["quote"]
        print(
            f"  {finding['file']}:{finding['line']}  "
            f"{finding['key']} = {quote}...{quote}"
        )
        print(f"    → {finding['match']}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - defensive CI boundary
        print(f"Secret scan: ERROR — {exc}", file=sys.stderr)
        sys.exit(2)
